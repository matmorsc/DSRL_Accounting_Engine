from __future__ import annotations

from pathlib import Path

import pandas as pd


VALID_OVERRIDE_TYPES = {
    "Approved Refund",
    "Reservation Modification",
    "Cash Received - Awaiting Deposit",
    "Booking.com Collection Issue",
    "Expected Future Manual Payment",
    "Expected Future Airbnb Payment",
    "Outside Reporting Scope",
    "Cancelled Reservation",
    "Accepted Difference",
}

REQUIRED_OVERRIDE_COLUMNS = {
    "reservation_id",
    "channel_reservation_id",
    "override_type",
    "effective_date",
    "amount",
    "notes",
    "status",
}


def _norm(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _read_overrides(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=sorted(REQUIRED_OVERRIDE_COLUMNS))

    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = sorted(REQUIRED_OVERRIDE_COLUMNS.difference(frame.columns))
    if missing:
        raise ValueError(f"Manual overrides missing columns: {missing}")

    frame = frame.copy()
    frame["override_type"] = frame["override_type"].astype(str).str.strip()
    frame["status"] = frame["status"].astype(str).str.strip()

    invalid = sorted(
        set(
            frame.loc[
                frame["override_type"].ne(""),
                "override_type",
            ]
        ).difference(VALID_OVERRIDE_TYPES)
    )
    if invalid:
        raise ValueError("Invalid override types: " + ", ".join(invalid))

    return frame.loc[
        ~frame["status"].str.lower().isin(
            {"inactive", "superseded", "void"}
        )
    ].copy()


def _select_override(
    reservation: pd.Series,
    overrides: pd.DataFrame,
) -> pd.Series | None:
    reservation_id = _norm(reservation.get("reservation_id"))
    channel_id = _norm(
        reservation.get("channel_reservation_id")
    )

    candidates = overrides.loc[
        (
            overrides["reservation_id"].astype(str).str.strip()
            .eq(reservation_id)
            & (reservation_id != "")
        )
        |
        (
            overrides["channel_reservation_id"].astype(str).str.strip()
            .eq(channel_id)
            & (channel_id != "")
        )
    ]

    if candidates.empty:
        return None
    if len(candidates) > 1:
        raise ValueError(
            "Multiple active overrides found for reservation "
            f"{reservation_id or channel_id}"
        )
    return candidates.iloc[0]


def _linked_payment_events(
    reservation: pd.Series,
    payment_ledger: pd.DataFrame,
) -> pd.DataFrame:
    reservation_id = _norm(reservation.get("reservation_id"))
    channel_id = _norm(
        reservation.get("channel_reservation_id")
    )

    return payment_ledger.loc[
        (
            payment_ledger["reservation_id"]
            .astype(str).str.strip().eq(reservation_id)
            & (reservation_id != "")
        )
        |
        (
            payment_ledger["channel_reservation_id"]
            .astype(str).str.strip().eq(channel_id)
            & (channel_id != "")
        )
    ].copy()


def _payment_totals(
    reservation: pd.Series,
    processor_transactions: pd.DataFrame,
) -> tuple[float, float]:
    reservation_id = _norm(reservation.get("reservation_id"))
    channel_id = _norm(
        reservation.get("channel_reservation_id")
    )

    linked = processor_transactions.loc[
        (
            processor_transactions["reservation_id"]
            .astype(str).str.strip().eq(reservation_id)
            & (reservation_id != "")
        )
        |
        (
            processor_transactions["channel_reservation_id"]
            .astype(str).str.strip().eq(channel_id)
            & (channel_id != "")
        )
    ].copy()

    payments = linked.loc[
        linked["transaction_type"].isin(
            {"charge", "payment", "reservation"}
        )
    ]
    refunds = linked.loc[
        linked["transaction_type"].eq("refund")
    ]

    return (
        round(payments["gross_amount"].abs().sum(), 2),
        round(refunds["gross_amount"].abs().sum(), 2),
    )


def _automatic_payment_status(
    reservation: pd.Series,
    match: pd.Series,
    acquisition_date: pd.Timestamp,
    today: pd.Timestamp,
    processor_payment_total: float,
    processor_refund_total: float,
    amount_tolerance: float,
) -> tuple[str, str, str]:
    source = _norm(reservation.get("source")).lower()
    payment_method = _norm(
        reservation.get("payment_method")
    ).lower()

    check_in = pd.to_datetime(
        reservation.get("check_in"), errors="coerce"
    )
    check_out = pd.to_datetime(
        reservation.get("check_out"), errors="coerce"
    )

    total_paid = float(reservation.get("total_paid", 0.0))
    total_refunded = float(
        reservation.get("total_refunded", 0.0)
    )
    balance_due = float(
        reservation.get("balance_due", 0.0)
    )
    match_status = _norm(match.get("match_status"))

    if pd.notna(check_out) and check_out < acquisition_date:
        return (
            "Outside Reporting Scope",
            "Expected / informational",
            "Reservation ended before acquisition date.",
        )

    if (
        source.startswith("airbnb")
        and pd.notna(check_out)
        and check_out.normalize() >= today.normalize()
        and processor_payment_total <= amount_tolerance
    ):
        return (
            "Expected Future Airbnb Payment",
            "Expected / informational",
            "Airbnb normally pays after checkout.",
        )

    if (
        payment_method in {"cash", "check", "cash / check"}
        and pd.notna(check_in)
        and check_in.normalize() >= today.normalize()
        and total_paid <= amount_tolerance
    ):
        return (
            "Expected Future Manual Payment",
            "Expected / informational",
            "Manual payment is expected at or near check-in.",
        )

    if (
        source.startswith("booking")
        and match_status == "No Processor Match"
        and (
            pd.isna(check_in)
            or check_in.normalize() <= today.normalize()
        )
    ):
        return (
            "Booking.com Collection Issue",
            "Needs operational follow-up",
            "Booking.com reservation has no processor match.",
        )

    if balance_due > amount_tolerance:
        return (
            "Balance Due",
            "Needs operational follow-up",
            "Guesty reports an unpaid balance.",
        )

    if payment_method in {"cash", "check", "cash / check"}:
        return (
            "Cash / Manual Review",
            "Needs human review",
            "Confirm collection and deposit status.",
        )

    if match_status in {
        "Single Legacy Candidate",
        "Multiple Legacy Candidates",
    }:
        return (
            match_status,
            "Needs human review",
            "Legacy Stripe candidate must be manually approved.",
        )

    if match_status == "No Processor Match":
        return (
            "No Payment Source Found",
            "Needs accounting follow-up",
            "No processor payment or legacy candidate was found.",
        )

    payment_difference = round(
        processor_payment_total - total_paid, 2
    )
    refund_difference = round(
        processor_refund_total - total_refunded, 2
    )

    if abs(refund_difference) > amount_tolerance:
        return (
            "Refund Discrepancy",
            "Needs accounting follow-up",
            f"Guesty and processor refunds differ by {refund_difference:.2f}.",
        )

    if abs(payment_difference) > amount_tolerance:
        return (
            "Payment Amount Mismatch",
            "Needs accounting follow-up",
            f"Guesty and processor payments differ by {payment_difference:.2f}.",
        )

    return (
        "Payment Resolved",
        "Ready for payout reconciliation",
        "Reservation and processor payment activity agree.",
    )


def _override_status(
    override: pd.Series,
) -> tuple[str, str, str]:
    override_type = _norm(override.get("override_type"))
    notes = _norm(override.get("notes"))

    categories = {
        "Approved Refund": "Documented business event",
        "Reservation Modification": "Documented business event",
        "Cash Received - Awaiting Deposit": "Needs operational follow-up",
        "Booking.com Collection Issue": "Needs operational follow-up",
        "Expected Future Manual Payment": "Expected / informational",
        "Expected Future Airbnb Payment": "Expected / informational",
        "Outside Reporting Scope": "Expected / informational",
        "Cancelled Reservation": "Documented business event",
        "Accepted Difference": "Documented business event",
    }

    return (
        override_type,
        categories.get(
            override_type,
            "Needs human review",
        ),
        notes or "Manual override applied.",
    )


def _lifecycle_details(
    linked_events: pd.DataFrame,
    payout_ledger: pd.DataFrame,
) -> dict[str, object]:
    if linked_events.empty:
        return {
            "payout_ids": "",
            "payout_dates": "",
            "payout_status": "No Linked Payment Event",
            "bank_transaction_ids": "",
            "bank_deposit_dates": "",
            "bank_status": "No Linked Payout",
            "all_payouts_allocated": False,
            "all_payouts_bank_matched": False,
        }

    assigned = linked_events.loc[
        linked_events["payout_assignment_status"].eq("Assigned")
        & linked_events["payout_id"].astype(str).str.strip().ne("")
    ]

    if assigned.empty:
        pending = linked_events[
            "payout_assignment_status"
        ].astype(str).str.strip().unique()

        return {
            "payout_ids": "",
            "payout_dates": "",
            "payout_status": (
                "Pending Future Payout"
                if "Pending Future Payout" in pending
                else "Payout Assignment Review"
            ),
            "bank_transaction_ids": "",
            "bank_deposit_dates": "",
            "bank_status": "No Linked Payout",
            "all_payouts_allocated": False,
            "all_payouts_bank_matched": False,
        }

    payout_ids = sorted(
        {
            _norm(value)
            for value in assigned["payout_id"]
            if _norm(value)
        }
    )

    linked_payouts = payout_ledger.loc[
        payout_ledger["payout_id"].astype(str).isin(payout_ids)
    ].copy()

    payout_dates = sorted(
        {
            pd.to_datetime(value).date().isoformat()
            for value in linked_payouts["transaction_date"]
            if pd.notna(pd.to_datetime(value, errors="coerce"))
        }
    )

    allocation_statuses = set(
        linked_payouts["allocation_status"]
        .astype(str).str.strip()
    )
    bank_statuses = set(
        linked_payouts["bank_match_status"]
        .astype(str).str.strip()
    )

    all_allocated = (
        not linked_payouts.empty
        and allocation_statuses == {"Fully Allocated"}
    )
    all_bank_matched = (
        not linked_payouts.empty
        and bank_statuses == {"Matched"}
    )

    bank_ids = sorted(
        {
            _norm(value)
            for value in linked_payouts["bank_transaction_id"]
            if _norm(value)
        }
    )
    bank_dates = sorted(
        {
            pd.to_datetime(value).date().isoformat()
            for value in linked_payouts["bank_transaction_date"]
            if pd.notna(pd.to_datetime(value, errors="coerce"))
        }
    )

    if all_allocated:
        payout_status = "Payout Fully Allocated"
    elif "Difference" in allocation_statuses:
        payout_status = "Payout Allocation Review"
    else:
        payout_status = "Payout Unallocated"

    bank_status = (
        "Deposit Matched"
        if all_bank_matched
        else "Deposit Missing or Review"
    )

    return {
        "payout_ids": " | ".join(payout_ids),
        "payout_dates": " | ".join(payout_dates),
        "payout_status": payout_status,
        "bank_transaction_ids": " | ".join(bank_ids),
        "bank_deposit_dates": " | ".join(bank_dates),
        "bank_status": bank_status,
        "all_payouts_allocated": all_allocated,
        "all_payouts_bank_matched": all_bank_matched,
    }


def _final_lifecycle_status(
    payment_status: str,
    payment_category: str,
    payout_status: str,
    bank_status: str,
    all_payouts_allocated: bool,
    all_payouts_bank_matched: bool,
) -> tuple[str, str]:
    if payment_category in {
        "Expected / informational",
        "Documented business event",
    }:
        return payment_status, "No"

    if payment_status != "Payment Resolved":
        return payment_status, "Yes"

    if payout_status == "Pending Future Payout":
        return "Payout Pending", "No"

    if not all_payouts_allocated:
        return "Payout Allocation Review", "Yes"

    if not all_payouts_bank_matched:
        return "Deposit Missing or Review", "Yes"

    return "Fully Reconciled", "No"


def build_reconciliation(
    reservations: pd.DataFrame,
    matches: pd.DataFrame,
    processor_transactions: pd.DataFrame,
    payment_ledger: pd.DataFrame,
    payout_ledger: pd.DataFrame,
    overrides_path: Path,
    acquisition_date: str,
    amount_tolerance: float = 0.02,
    as_of_date: str | None = None,
) -> pd.DataFrame:
    if len(reservations) != len(matches):
        raise ValueError(
            "Reservation and match row counts do not agree."
        )

    overrides = _read_overrides(overrides_path)
    acquisition = pd.to_datetime(
        acquisition_date, errors="raise"
    )
    today = (
        pd.to_datetime(as_of_date, errors="raise")
        if as_of_date
        else pd.Timestamp.today()
    )

    rows: list[dict[str, object]] = []

    for index, reservation in reservations.iterrows():
        match = matches.iloc[index]
        override = _select_override(
            reservation, overrides
        )

        processor_payment_total, processor_refund_total = (
            _payment_totals(
                reservation,
                processor_transactions,
            )
        )

        if override is not None:
            payment_status, category, explanation = (
                _override_status(override)
            )
            override_type = _norm(
                override.get("override_type")
            )
            override_notes = _norm(
                override.get("notes")
            )
            override_amount = pd.to_numeric(
                override.get("amount"),
                errors="coerce",
            )
        else:
            payment_status, category, explanation = (
                _automatic_payment_status(
                    reservation=reservation,
                    match=match,
                    acquisition_date=acquisition,
                    today=today,
                    processor_payment_total=processor_payment_total,
                    processor_refund_total=processor_refund_total,
                    amount_tolerance=amount_tolerance,
                )
            )
            override_type = ""
            override_notes = ""
            override_amount = float("nan")

        linked_events = _linked_payment_events(
            reservation, payment_ledger
        )
        lifecycle = _lifecycle_details(
            linked_events, payout_ledger
        )

        final_status, review_required = (
            _final_lifecycle_status(
                payment_status=payment_status,
                payment_category=category,
                payout_status=str(
                    lifecycle["payout_status"]
                ),
                bank_status=str(
                    lifecycle["bank_status"]
                ),
                all_payouts_allocated=bool(
                    lifecycle["all_payouts_allocated"]
                ),
                all_payouts_bank_matched=bool(
                    lifecycle["all_payouts_bank_matched"]
                ),
            )
        )

        rows.append(
            {
                "reconciliation_id": _norm(
                    match.get("reconciliation_id")
                ),
                "reservation_id": _norm(
                    reservation.get("reservation_id")
                ),
                "channel_reservation_id": _norm(
                    reservation.get(
                        "channel_reservation_id"
                    )
                ),
                "guest": _norm(
                    reservation.get("guest")
                ),
                "listing": _norm(
                    reservation.get("listing")
                ),
                "property_class": _norm(
                    reservation.get("property_class")
                ),
                "income_account": _norm(
                    reservation.get("income_account")
                ),
                "source": _norm(
                    reservation.get("source")
                ),
                "payment_method": _norm(
                    reservation.get("payment_method")
                ),
                "confirmation_date": reservation.get(
                    "confirmation_date"
                ),
                "check_in": reservation.get("check_in"),
                "check_out": reservation.get("check_out"),
                "guesty_total_paid": float(
                    reservation.get("total_paid", 0.0)
                ),
                "guesty_total_refunded": float(
                    reservation.get(
                        "total_refunded", 0.0
                    )
                ),
                "guesty_balance_due": float(
                    reservation.get("balance_due", 0.0)
                ),
                "processor_payment_total": (
                    processor_payment_total
                ),
                "processor_refund_total": (
                    processor_refund_total
                ),
                "payment_difference": round(
                    processor_payment_total
                    - float(
                        reservation.get("total_paid", 0.0)
                    ),
                    2,
                ),
                "refund_difference": round(
                    processor_refund_total
                    - float(
                        reservation.get(
                            "total_refunded", 0.0
                        )
                    ),
                    2,
                ),
                "match_status": _norm(
                    match.get("match_status")
                ),
                "match_method": _norm(
                    match.get("match_method")
                ),
                "confidence_score": int(
                    match.get(
                        "confidence_score", 0
                    )
                ),
                "payment_status": payment_status,
                "payment_status_category": category,
                "payment_status_explanation": explanation,
                "payout_ids": lifecycle["payout_ids"],
                "payout_dates": lifecycle["payout_dates"],
                "payout_status": lifecycle["payout_status"],
                "bank_transaction_ids": lifecycle[
                    "bank_transaction_ids"
                ],
                "bank_deposit_dates": lifecycle[
                    "bank_deposit_dates"
                ],
                "bank_status": lifecycle["bank_status"],
                "override_type": override_type,
                "override_amount": override_amount,
                "override_notes": override_notes,
                "lifecycle_status": final_status,
                "review_required": review_required,
                "as_of_date": today.normalize(),
            }
        )

    return pd.DataFrame(rows)
