from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd


REQUIRED_POSTING_COLUMNS = {
    "payout_id",
    "processor",
    "payout_date",
    "payout_amount",
    "bank_transaction_id",
    "bank_transaction_date",
    "bank_amount",
    "posting_status",
    "generate_entry",
}

REQUIRED_PAYOUT_COLUMNS = {
    "payout_id",
    "processor",
    "processor_account",
    "transaction_date",
    "payout_amount",
    "bank_transaction_id",
    "bank_transaction_date",
    "bank_amount",
}

REQUIRED_PAYMENT_COLUMNS = {
    "payment_event_id",
    "processor",
    "processor_account",
    "transaction_id",
    "transaction_type",
    "gross_amount",
    "processor_fee",
    "net_amount",
    "reservation_id",
    "channel_reservation_id",
    "payout_id",
    "payout_assignment_status",
}

REQUIRED_RESERVATION_COLUMNS = {
    "reservation_id",
    "channel_reservation_id",
    "guest",
    "listing",
    "property_class",
    "income_account",
    "accommodation_revenue",
    "state_tax",
    "county_tax",
    "local_tax",
    "total_paid",
    "total_refunded",
}


def _require(
    frame: pd.DataFrame,
    required: set[str],
    label: str,
) -> None:
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


def _text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def _money(value: object) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def _date(value: object) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(parsed) else parsed.date().isoformat()


def _lookup_reservation(
    reservation_id: str,
    channel_id: str,
    by_reservation_id: dict[str, pd.Series],
    by_channel_id: dict[str, pd.Series],
) -> pd.Series | None:
    if reservation_id and reservation_id in by_reservation_id:
        return by_reservation_id[reservation_id]
    if channel_id and channel_id in by_channel_id:
        return by_channel_id[channel_id]
    return None


def _event_amounts(events: pd.DataFrame) -> tuple[float, float, float]:
    transaction_types = (
        events["transaction_type"].astype(str).str.lower().str.strip()
    )

    positive = events.loc[
        transaction_types.isin({"charge", "payment", "reservation"})
    ]
    refunds = events.loc[transaction_types.eq("refund")]

    positive_gross = round(
        positive["gross_amount"].astype(float).abs().sum(),
        2,
    )
    refund_gross = round(
        refunds["gross_amount"].astype(float).abs().sum(),
        2,
    )
    fees = round(
        events["processor_fee"].astype(float).abs().sum(),
        2,
    )

    return positive_gross, refund_gross, fees


def _allocation_basis(
    reservation: pd.Series,
    processor: str,
    marketplace_processors: set[str],
) -> float:
    if processor in marketplace_processors:
        return max(
            _money(reservation.get("accommodation_revenue"))
            - _money(reservation.get("total_refunded")),
            0.0,
        )

    total_paid = _money(reservation.get("total_paid"))
    if total_paid > 0:
        return total_paid

    return (
        _money(reservation.get("accommodation_revenue"))
        + _money(reservation.get("state_tax"))
        + _money(reservation.get("county_tax"))
        + _money(reservation.get("local_tax"))
    )


def _add_line(
    lines: list[dict[str, Any]],
    *,
    payout_id: str,
    line_number: int,
    line_type: str,
    account: str,
    description: str,
    amount: float,
    qb_class: str,
    reservation_id: str = "",
    channel_reservation_id: str = "",
    guest: str = "",
    listing: str = "",
) -> None:
    if abs(amount) < 0.005:
        return

    lines.append(
        {
            "payout_id": payout_id,
            "line_number": line_number,
            "line_type": line_type,
            "account": account,
            "description": description,
            "amount": round(amount, 2),
            "class": qb_class,
            "reservation_id": reservation_id,
            "channel_reservation_id": channel_reservation_id,
            "guest": guest,
            "listing": listing,
        }
    )


def build_deposit_drafts(
    *,
    posting_status: pd.DataFrame,
    payout_ledger: pd.DataFrame,
    payment_ledger: pd.DataFrame,
    reservations: pd.DataFrame,
    rules: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    _require(
        posting_status,
        REQUIRED_POSTING_COLUMNS,
        "Posting status",
    )
    _require(
        payout_ledger,
        REQUIRED_PAYOUT_COLUMNS,
        "Payout ledger",
    )
    _require(
        payment_ledger,
        REQUIRED_PAYMENT_COLUMNS,
        "Payment ledger",
    )
    _require(
        reservations,
        REQUIRED_RESERVATION_COLUMNS,
        "Reservations",
    )

    tolerance = float(rules.get("amount_tolerance", 0.02))
    classes = rules.get("classes", {})
    accounts = rules.get("accounts", {})
    fee_accounts = rules.get("processor_fee_accounts", {})
    tax_descriptions = rules.get("tax_descriptions", {})
    marketplace_processors = set(
        rules.get("marketplace_remitted_tax_processors", [])
    )

    by_reservation_id = {
        _text(row["reservation_id"]): row
        for _, row in reservations.iterrows()
        if _text(row["reservation_id"])
    }
    by_channel_id = {
        _text(row["channel_reservation_id"]): row
        for _, row in reservations.iterrows()
        if _text(row["channel_reservation_id"])
    }

    eligible = posting_status.loc[
        posting_status["generate_entry"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("yes")
    ].copy()

    payout_by_id = {
        _text(row["payout_id"]): row
        for _, row in payout_ledger.iterrows()
    }

    summaries: list[dict[str, Any]] = []
    all_lines: list[dict[str, Any]] = []

    for _, posting in eligible.iterrows():
        payout_id = _text(posting["payout_id"])
        payout = payout_by_id.get(payout_id)

        if payout is None:
            summaries.append(
                {
                    "payout_id": payout_id,
                    "processor": _text(posting.get("processor")),
                    "deposit_date": _date(
                        posting.get("bank_transaction_date")
                    ),
                    "bank_transaction_id": _text(
                        posting.get("bank_transaction_id")
                    ),
                    "bank_amount": _money(posting.get("bank_amount")),
                    "draft_total": 0.0,
                    "difference": round(
                        -_money(posting.get("bank_amount")),
                        2,
                    ),
                    "balanced": "No",
                    "draft_status": "Review Required",
                    "review_reason": "Payout missing from payout ledger.",
                    "line_count": 0,
                    "source_reservation_count": 0,
                }
            )
            continue

        processor = _text(payout.get("processor"))
        bank_amount = _money(
            payout.get("bank_amount")
            or payout.get("payout_amount")
        )
        deposit_date = _date(
            payout.get("bank_transaction_date")
            or payout.get("transaction_date")
        )

        events = payment_ledger.loc[
            payment_ledger["payout_id"]
            .astype(str)
            .str.strip()
            .eq(payout_id)
            & payment_ledger["payout_assignment_status"]
            .astype(str)
            .str.strip()
            .eq("Assigned")
        ].copy()

        grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
        for idx, event in events.iterrows():
            key = (
                _text(event.get("reservation_id")),
                _text(event.get("channel_reservation_id")),
            )
            grouped[key].append(idx)

        draft_lines: list[dict[str, Any]] = []
        unresolved_events = 0
        missing_mappings: list[str] = []
        reservation_count = 0
        line_number = 1
        total_fees = 0.0

        for (reservation_id, channel_id), indices in grouped.items():
            reservation = _lookup_reservation(
                reservation_id,
                channel_id,
                by_reservation_id,
                by_channel_id,
            )

            reservation_events = events.loc[indices]
            positive_gross, refund_gross, event_fees = _event_amounts(
                reservation_events
            )
            total_fees += event_fees

            if reservation is None:
                unresolved_events += len(indices)
                continue

            reservation_count += 1
            property_class = _text(
                reservation.get("property_class")
            )
            qb_class = _text(classes.get(property_class))

            if not qb_class:
                missing_mappings.append(
                    f"class mapping for {property_class or 'blank property class'}"
                )

            income_account = _text(
                reservation.get("income_account")
            )
            if not income_account:
                missing_mappings.append(
                    f"income account for reservation {reservation_id or channel_id}"
                )

            basis = _allocation_basis(
                reservation,
                processor,
                marketplace_processors,
            )

            ratio = (
                min(positive_gross / basis, 1.0)
                if basis > 0 and positive_gross > 0
                else 0.0
            )

            revenue_amount = round(
                _money(
                    reservation.get("accommodation_revenue")
                )
                * ratio,
                2,
            )

            _add_line(
                draft_lines,
                payout_id=payout_id,
                line_number=line_number,
                line_type="Revenue",
                account=income_account,
                description=_text(reservation.get("listing")),
                amount=revenue_amount,
                qb_class=qb_class,
                reservation_id=_text(
                    reservation.get("reservation_id")
                ),
                channel_reservation_id=_text(
                    reservation.get("channel_reservation_id")
                ),
                guest=_text(reservation.get("guest")),
                listing=_text(reservation.get("listing")),
            )
            if abs(revenue_amount) >= 0.005:
                line_number += 1

            if processor not in marketplace_processors:
                tax_account = _text(accounts.get("tax_payable"))
                tax_class = _text(classes.get("tax"))

                if not tax_account:
                    missing_mappings.append("tax payable account")
                if not tax_class:
                    missing_mappings.append("tax class")

                for field in ("state_tax", "county_tax", "local_tax"):
                    tax_amount = round(
                        _money(reservation.get(field)) * ratio,
                        2,
                    )
                    _add_line(
                        draft_lines,
                        payout_id=payout_id,
                        line_number=line_number,
                        line_type="Tax",
                        account=tax_account,
                        description=_text(
                            tax_descriptions.get(field, field)
                        ),
                        amount=tax_amount,
                        qb_class=tax_class,
                        reservation_id=_text(
                            reservation.get("reservation_id")
                        ),
                        channel_reservation_id=_text(
                            reservation.get(
                                "channel_reservation_id"
                            )
                        ),
                        guest=_text(reservation.get("guest")),
                        listing=_text(reservation.get("listing")),
                    )
                    if abs(tax_amount) >= 0.005:
                        line_number += 1

            if refund_gross > 0:
                refund_account = _text(accounts.get("refunds"))
                refund_class = _text(classes.get("refunds"))

                if not refund_account:
                    missing_mappings.append("refund account")
                if not refund_class:
                    missing_mappings.append("refund class")

                _add_line(
                    draft_lines,
                    payout_id=payout_id,
                    line_number=line_number,
                    line_type="Refund",
                    account=refund_account,
                    description="Processor refund",
                    amount=-refund_gross,
                    qb_class=refund_class,
                    reservation_id=_text(
                        reservation.get("reservation_id")
                    ),
                    channel_reservation_id=_text(
                        reservation.get("channel_reservation_id")
                    ),
                    guest=_text(reservation.get("guest")),
                    listing=_text(reservation.get("listing")),
                )
                line_number += 1

        if total_fees > 0:
            fee_account = _text(fee_accounts.get(processor))
            fee_class = _text(classes.get("fees"))

            if not fee_account:
                missing_mappings.append(
                    f"fee account for {processor or 'blank processor'}"
                )
            if not fee_class:
                missing_mappings.append("fee class")

            _add_line(
                draft_lines,
                payout_id=payout_id,
                line_number=line_number,
                line_type="Processor Fee",
                account=fee_account,
                description=f"{processor} processing fees",
                amount=-total_fees,
                qb_class=fee_class,
            )

        draft_total = round(
            sum(float(line["amount"]) for line in draft_lines),
            2,
        )
        difference = round(draft_total - bank_amount, 2)
        balanced = abs(difference) <= tolerance

        review_reasons: list[str] = []
        if events.empty:
            review_reasons.append(
                "No assigned payment events found for payout."
            )
        if unresolved_events:
            review_reasons.append(
                f"{unresolved_events} payment event(s) could not be linked to a reservation."
            )
        if missing_mappings:
            review_reasons.append(
                "Missing configuration: "
                + "; ".join(sorted(set(missing_mappings)))
                + "."
            )
        if not balanced:
            review_reasons.append(
                f"Draft differs from bank amount by {difference:.2f}."
            )

        draft_status = (
            "Ready for Review"
            if not review_reasons
            else "Review Required"
        )

        all_lines.extend(draft_lines)
        summaries.append(
            {
                "payout_id": payout_id,
                "processor": processor,
                "processor_account": _text(
                    payout.get("processor_account")
                ),
                "deposit_date": deposit_date,
                "bank_transaction_id": _text(
                    payout.get("bank_transaction_id")
                ),
                "bank_amount": bank_amount,
                "draft_total": draft_total,
                "difference": difference,
                "balanced": "Yes" if balanced else "No",
                "draft_status": draft_status,
                "review_reason": " ".join(review_reasons),
                "line_count": len(draft_lines),
                "source_reservation_count": reservation_count,
                "posting_status": _text(
                    posting.get("posting_status")
                ),
            }
        )

    summary_columns = [
        "payout_id",
        "processor",
        "processor_account",
        "deposit_date",
        "bank_transaction_id",
        "bank_amount",
        "draft_total",
        "difference",
        "balanced",
        "draft_status",
        "review_reason",
        "line_count",
        "source_reservation_count",
        "posting_status",
    ]

    line_columns = [
        "payout_id",
        "line_number",
        "line_type",
        "account",
        "description",
        "amount",
        "class",
        "reservation_id",
        "channel_reservation_id",
        "guest",
        "listing",
    ]

    return (
        pd.DataFrame(summaries, columns=summary_columns),
        pd.DataFrame(all_lines, columns=line_columns),
    )
