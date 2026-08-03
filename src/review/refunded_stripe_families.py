from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pandas as pd


HISTORY_COLUMNS = [
    "posting_line_id",
    "posting_group_id",
    "payment_event_id",
    "processor",
    "processor_account",
    "transaction_id",
    "transaction_type",
    "transaction_date",
    "source_id",
    "payout_id",
    "reservation_id",
    "channel_reservation_id",
    "guest",
    "listing",
    "account",
    "class",
    "description",
    "signed_amount",
    "posting_type",
    "reversal_of_posting_line_id",
    "classification_source",
    "created_by",
    "created_at",
    "status",
    "notes",
]

PREVIEW_COLUMNS = [
    "resolution_group_id",
    "payout_id",
    "source_id",
    "guest",
    "listing",
    "charge_net",
    "refund_total",
    "adjustment_total",
    "processor_fee",
    "family_net",
    "proposed_total",
    "validation_status",
    "duplicate_line_count",
    "lines_to_promote",
    "validation_detail",
]


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


def _stable_id(prefix: str, parts: list[str]) -> str:
    digest = hashlib.sha256(
        "|".join(parts).encode("utf-8")
    ).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _ensure_history_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in HISTORY_COLUMNS:
        if column not in result.columns:
            result[column] = ""
    return result[HISTORY_COLUMNS]


def build_refunded_family_candidates(
    *,
    payment_ledger: pd.DataFrame,
    reservations: pd.DataFrame,
) -> pd.DataFrame:
    if payment_ledger.empty:
        return pd.DataFrame()

    reservation_lookup = {
        _text(row.get("reservation_id")): row
        for _, row in reservations.iterrows()
        if _text(row.get("reservation_id"))
    }

    rows = []

    grouped = payment_ledger.groupby(
        ["payout_id", "source_id"],
        dropna=False,
    )

    for (payout_id_raw, source_id_raw), family in grouped:
        payout_id = _text(payout_id_raw)
        source_id = _text(source_id_raw)

        if not payout_id or not source_id:
            continue

        if not family["processor"].astype(str).str.strip().eq("Stripe").all():
            continue

        types = family["transaction_type"].astype(str).str.strip().str.lower()

        charges = family.loc[types.eq("charge")].copy()
        refunds = family.loc[types.eq("refund")].copy()
        adjustments = family.loc[types.eq("adjustment")].copy()

        if len(charges) != 1 or refunds.empty:
            continue

        charge = charges.iloc[0]
        reservation_id = _text(charge.get("reservation_id"))
        reservation = reservation_lookup.get(reservation_id)

        if reservation is None:
            continue

        reservation_revenue = _money(
            reservation.get("accommodation_revenue")
        )
        reservation_paid = _money(
            reservation.get("total_paid")
        )
        reservation_refunded = _money(
            reservation.get("total_refunded")
        )
        reservation_payout = _money(
            reservation.get("total_payout")
        )

        charge_gross = _money(charge.get("gross_amount"))
        charge_fee = _money(charge.get("processor_fee"))
        charge_net = _money(charge.get("net_amount"))
        refund_total = _money(
            pd.to_numeric(
                refunds["net_amount"],
                errors="coerce",
            ).fillna(0.0).sum()
        )
        adjustment_total = _money(
            pd.to_numeric(
                adjustments.get(
                    "net_amount",
                    pd.Series(dtype=float),
                ),
                errors="coerce",
            ).fillna(0.0).sum()
        )
        family_net = round(
            charge_net + refund_total + adjustment_total,
            2,
        )

        fully_refunded = (
            abs(reservation_revenue) <= 0.02
            and abs(reservation_paid) <= 0.02
            and abs(reservation_payout) <= 0.02
            and abs(
                reservation_refunded - charge_gross
            ) <= 0.02
        )

        eligible = (
            fully_refunded
            and charge_fee > 0
            and family_net < 0
        )

        group_id = _stable_id(
            "refundfam",
            [payout_id, source_id],
        )

        rows.append(
            {
                "resolution_group_id": group_id,
                "payment_event_id": _text(
                    charge.get("payment_event_id")
                ),
                "processor_account": _text(
                    charge.get("processor_account")
                ),
                "transaction_id": _text(
                    charge.get("transaction_id")
                ),
                "transaction_date": _text(
                    charge.get("transaction_date")
                ),
                "payout_id": payout_id,
                "source_id": source_id,
                "reservation_id": reservation_id,
                "channel_reservation_id": _text(
                    charge.get("channel_reservation_id")
                ),
                "guest": _text(charge.get("guest")),
                "listing": _text(charge.get("listing")),
                "charge_gross": charge_gross,
                "charge_net": charge_net,
                "processor_fee": charge_fee,
                "refund_total": refund_total,
                "adjustment_total": adjustment_total,
                "family_net": family_net,
                "reservation_revenue": reservation_revenue,
                "reservation_paid": reservation_paid,
                "reservation_refunded": reservation_refunded,
                "reservation_payout": reservation_payout,
                "approval_eligible": "Yes" if eligible else "No",
                "approval_status": "Pending" if eligible else "Not Eligible",
                "review_notes": (
                    "Fully refunded reservation; retain only processor-fee economics."
                    if eligible
                    else "Family did not meet fully refunded controls."
                ),
            }
        )

    return pd.DataFrame(rows)


def _history_rows(
    approval: pd.Series,
    *,
    created_at: str,
) -> list[dict[str, object]]:
    group_id = _text(approval.get("resolution_group_id"))
    fee = _money(approval.get("processor_fee"))
    adjustment = _money(approval.get("adjustment_total"))

    allocations = [
        (
            "Retained Stripe processing fee",
            -abs(fee),
            "Processor Fee Loss",
        )
    ]

    if abs(adjustment) > 0.005:
        allocations.append(
            (
                "Stripe fee adjustment credit",
                adjustment,
                "Processor Fee Adjustment",
            )
        )

    rows = []
    for index, (description, amount, allocation_type) in enumerate(
        allocations,
        start=1,
    ):
        rows.append(
            {
                "posting_line_id": _stable_id(
                    "pl",
                    [group_id, str(index), allocation_type],
                ),
                "posting_group_id": _stable_id(
                    "pg",
                    [group_id],
                ),
                "payment_event_id": _text(
                    approval.get("payment_event_id")
                ),
                "processor": "Stripe",
                "processor_account": _text(
                    approval.get("processor_account")
                ),
                "transaction_id": _text(
                    approval.get("transaction_id")
                ),
                "transaction_type": "source_event",
                "transaction_date": _text(
                    approval.get("transaction_date")
                ),
                "source_id": _text(
                    approval.get("source_id")
                ),
                "payout_id": _text(
                    approval.get("payout_id")
                ),
                "reservation_id": _text(
                    approval.get("reservation_id")
                ),
                "channel_reservation_id": _text(
                    approval.get("channel_reservation_id")
                ),
                "guest": _text(
                    approval.get("guest")
                ),
                "listing": _text(
                    approval.get("listing")
                ),
                "account": (
                    "Bank Charges & Fees:"
                    "Stripe Processing Fees"
                ),
                "class": (
                    "RV Sites"
                    if "rv" in _text(
                        approval.get("listing")
                    ).lower()
                    else "Hospitality"
                ),
                "description": description,
                "signed_amount": amount,
                "posting_type": "Source Event",
                "reversal_of_posting_line_id": "",
                "classification_source": (
                    "Fully Refunded Stripe Family"
                ),
                "created_by": (
                    "DSRL Accounting Engine V11H"
                ),
                "created_at": created_at,
                "status": "Active",
                "notes": (
                    "Fully refunded Stripe family. "
                    "No revenue remains; only retained fee "
                    "and Stripe adjustment economics are posted."
                ),
            }
        )

    return rows


def preview_refunded_family_promotion(
    *,
    approvals: pd.DataFrame,
    existing_history: pd.DataFrame,
    tolerance: float = 0.02,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    history = _ensure_history_columns(existing_history)
    existing_ids = set(
        history["posting_line_id"]
        .astype(str)
        .str.strip()
    )

    approved = (
        approvals.loc[
            approvals["approval_status"]
            .astype(str)
            .str.strip()
            .eq("Approved")
        ].copy()
        if not approvals.empty
        else pd.DataFrame()
    )

    preview_rows = []
    proposed_rows = []
    created_at = datetime.now(
        timezone.utc
    ).replace(microsecond=0).isoformat()

    for _, approval in approved.iterrows():
        valid = True
        details = []

        if _text(
            approval.get("approval_eligible")
        ) != "Yes":
            valid = False
            details.append(
                "Approval row is not eligible."
            )

        proposed = _history_rows(
            approval,
            created_at=created_at,
        )

        proposed_total = round(
            sum(
                _money(row["signed_amount"])
                for row in proposed
            ),
            2,
        )
        family_net = _money(
            approval.get("family_net")
        )

        if abs(proposed_total - family_net) > tolerance:
            valid = False
            details.append(
                f"Proposed total {proposed_total:.2f} "
                f"does not match family net {family_net:.2f}."
            )

        duplicate_count = sum(
            1
            for row in proposed
            if row["posting_line_id"] in existing_ids
        )

        if duplicate_count not in {0, len(proposed)}:
            valid = False
            details.append(
                "Refunded-family group is partially duplicated."
            )

        if valid and duplicate_count == 0:
            status = "Ready to Promote"
            lines_to_promote = len(proposed)
            proposed_rows.extend(proposed)
        elif valid and duplicate_count == len(proposed):
            status = "Already Promoted"
            lines_to_promote = 0
            details.append(
                "All source-event lines already exist."
            )
        else:
            status = "Blocked"
            lines_to_promote = 0

        preview_rows.append(
            {
                "resolution_group_id": _text(
                    approval.get("resolution_group_id")
                ),
                "payout_id": _text(
                    approval.get("payout_id")
                ),
                "source_id": _text(
                    approval.get("source_id")
                ),
                "guest": _text(
                    approval.get("guest")
                ),
                "listing": _text(
                    approval.get("listing")
                ),
                "charge_net": _money(
                    approval.get("charge_net")
                ),
                "refund_total": _money(
                    approval.get("refund_total")
                ),
                "adjustment_total": _money(
                    approval.get("adjustment_total")
                ),
                "processor_fee": _money(
                    approval.get("processor_fee")
                ),
                "family_net": family_net,
                "proposed_total": proposed_total,
                "validation_status": status,
                "duplicate_line_count": duplicate_count,
                "lines_to_promote": lines_to_promote,
                "validation_detail": (
                    " ".join(details)
                    or "All refunded-family controls passed."
                ),
            }
        )

    return (
        pd.DataFrame(
            preview_rows,
            columns=PREVIEW_COLUMNS,
        ),
        pd.DataFrame(
            proposed_rows,
            columns=HISTORY_COLUMNS,
        ),
    )


def apply_refunded_family_promotion(
    *,
    approvals: pd.DataFrame,
    existing_history: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    preview, proposed = (
        preview_refunded_family_promotion(
            approvals=approvals,
            existing_history=existing_history,
        )
    )

    blocked = preview.loc[
        preview["validation_status"]
        .astype(str)
        .eq("Blocked")
    ]
    if not blocked.empty:
        raise ValueError(
            "One or more Approved refunded-family groups "
            "failed validation. No history was modified."
        )

    history = _ensure_history_columns(
        existing_history
    )
    updated_history = (
        pd.concat(
            [history, proposed],
            ignore_index=True,
            sort=False,
        )[HISTORY_COLUMNS]
        if not proposed.empty
        else history
    )

    updated_approvals = approvals.copy()
    completed = set(
        preview.loc[
            preview["validation_status"].isin(
                [
                    "Ready to Promote",
                    "Already Promoted",
                ]
            ),
            "resolution_group_id",
        ].astype(str)
    )

    for index, row in updated_approvals.iterrows():
        if _text(
            row.get("resolution_group_id")
        ) in completed:
            updated_approvals.at[
                index,
                "approval_status",
            ] = "Promoted"

    return (
        preview,
        updated_history,
        updated_approvals,
    )
