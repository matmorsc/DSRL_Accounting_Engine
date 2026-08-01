from __future__ import annotations

from typing import Any

import pandas as pd


REQUIRED_POSTING_COLUMNS = {
    "payout_id",
    "processor",
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

REQUIRED_ALLOCATION_COLUMNS = {
    "payment_event_id",
    "payout_id",
    "processor",
    "reservation_id",
    "channel_reservation_id",
    "guest",
    "listing",
    "allocation_type",
    "account",
    "description",
    "amount",
    "class",
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


def build_deposit_drafts_v2(
    *,
    posting_status: pd.DataFrame,
    payout_ledger: pd.DataFrame,
    allocations: pd.DataFrame,
    rules: dict[str, Any],
    payout_adjustments: pd.DataFrame | None = None,
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
        allocations,
        REQUIRED_ALLOCATION_COLUMNS,
        "Payment allocations",
    )

    tolerance = float(rules.get("amount_tolerance", 0.02))

    if payout_adjustments is None:
        payout_adjustments = pd.DataFrame(
            columns=[
                "payout_id",
                "adjustment_type",
                "amount",
                "account",
                "class",
                "description",
                "status",
                "notes",
            ]
        )

    eligible = posting_status.loc[
        posting_status["generate_entry"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("yes")
    ].copy()

    payout_index = {
        _text(row["payout_id"]): row
        for _, row in payout_ledger.iterrows()
    }

    summary_rows: list[dict[str, object]] = []
    line_rows: list[dict[str, object]] = []

    for _, posting in eligible.iterrows():
        payout_id = _text(posting.get("payout_id"))
        payout = payout_index.get(payout_id)

        if payout is None:
            continue

        payout_allocations = allocations.loc[
            allocations["payout_id"]
            .astype(str)
            .str.strip()
            .eq(payout_id)
        ].copy()

        grouped = (
            payout_allocations.groupby(
                [
                    "allocation_type",
                    "account",
                    "description",
                    "class",
                ],
                dropna=False,
            )
            .agg(
                amount=("amount", "sum"),
                source_event_count=(
                    "payment_event_id",
                    "nunique",
                ),
                source_reservation_count=(
                    "reservation_id",
                    "nunique",
                ),
            )
            .reset_index()
        )

        grouped["amount"] = grouped["amount"].round(2)
        grouped = grouped.loc[
            grouped["amount"].abs().ge(0.005)
        ].reset_index(drop=True)

        adjustment_rows = payout_adjustments.loc[
            payout_adjustments["payout_id"]
            .astype(str)
            .str.strip()
            .eq(payout_id)
        ].copy()

        line_number = 1

        for _, line in grouped.iterrows():
            line_rows.append(
                {
                    "payout_id": payout_id,
                    "line_number": line_number,
                    "line_type": _text(
                        line.get("allocation_type")
                    ),
                    "account": _text(
                        line.get("account")
                    ),
                    "description": _text(
                        line.get("description")
                    ),
                    "amount": _money(line.get("amount")),
                    "class": _text(line.get("class")),
                    "source_event_count": int(
                        line.get("source_event_count", 0)
                    ),
                    "source_reservation_count": int(
                        line.get(
                            "source_reservation_count",
                            0,
                        )
                    ),
                    "override_source": "",
                }
            )
            line_number += 1

        for _, adjustment in adjustment_rows.iterrows():
            line_rows.append(
                {
                    "payout_id": payout_id,
                    "line_number": line_number,
                    "line_type": (
                        "Manual Adjustment: "
                        + _text(
                            adjustment.get(
                                "adjustment_type"
                            )
                        )
                    ),
                    "account": _text(
                        adjustment.get("account")
                    ),
                    "description": _text(
                        adjustment.get("description")
                    ),
                    "amount": _money(
                        adjustment.get("amount")
                    ),
                    "class": _text(
                        adjustment.get("class")
                    ),
                    "source_event_count": 0,
                    "source_reservation_count": 0,
                    "override_source": (
                        "config/payout_adjustments.csv"
                    ),
                }
            )
            line_number += 1

        bank_amount = _money(
            payout.get("bank_amount")
            or payout.get("payout_amount")
        )

        allocation_total = round(
            grouped["amount"].sum()
            if not grouped.empty
            else 0.0,
            2,
        )
        adjustment_total = round(
            pd.to_numeric(
                adjustment_rows.get(
                    "amount",
                    pd.Series(dtype=float),
                ),
                errors="coerce",
            )
            .fillna(0.0)
            .sum(),
            2,
        )

        draft_total = round(
            allocation_total + adjustment_total,
            2,
        )
        difference = round(draft_total - bank_amount, 2)
        balanced = abs(difference) <= tolerance

        missing_account_lines = int(
            grouped["account"]
            .astype(str)
            .str.strip()
            .eq("")
            .sum()
        ) if not grouped.empty else 0

        missing_class_lines = int(
            grouped["class"]
            .astype(str)
            .str.strip()
            .eq("")
            .sum()
        ) if not grouped.empty else 0

        if not adjustment_rows.empty:
            missing_account_lines += int(
                adjustment_rows["account"]
                .astype(str)
                .str.strip()
                .eq("")
                .sum()
            )
            missing_class_lines += int(
                adjustment_rows["class"]
                .astype(str)
                .str.strip()
                .eq("")
                .sum()
            )

        reasons: list[str] = []

        if grouped.empty and adjustment_rows.empty:
            reasons.append(
                "No payment allocations or adjustments were available for this payout."
            )
        if missing_account_lines:
            reasons.append(
                f"{missing_account_lines} draft line(s) have no account."
            )
        if missing_class_lines:
            reasons.append(
                f"{missing_class_lines} draft line(s) have no class."
            )
        if not balanced:
            reasons.append(
                f"Draft differs from bank amount by {difference:.2f}."
            )

        summary_rows.append(
            {
                "payout_id": payout_id,
                "processor": _text(
                    payout.get("processor")
                ),
                "processor_account": _text(
                    payout.get("processor_account")
                ),
                "deposit_date": _date(
                    payout.get("bank_transaction_date")
                    or payout.get("transaction_date")
                ),
                "bank_transaction_id": _text(
                    payout.get("bank_transaction_id")
                ),
                "bank_amount": bank_amount,
                "allocation_total": allocation_total,
                "manual_adjustment_total": adjustment_total,
                "draft_total": draft_total,
                "difference": difference,
                "balanced": "Yes" if balanced else "No",
                "draft_status": (
                    "Ready for Review"
                    if not reasons
                    else "Review Required"
                ),
                "review_reason": " ".join(reasons),
                "line_count": len(grouped) + len(adjustment_rows),
                "source_event_count": int(
                    payout_allocations[
                        "payment_event_id"
                    ].nunique()
                ),
                "source_reservation_count": int(
                    payout_allocations[
                        "reservation_id"
                    ].nunique()
                ),
                "manual_adjustment_count": len(
                    adjustment_rows
                ),
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
        "allocation_total",
        "manual_adjustment_total",
        "draft_total",
        "difference",
        "balanced",
        "draft_status",
        "review_reason",
        "line_count",
        "source_event_count",
        "source_reservation_count",
        "manual_adjustment_count",
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
        "source_event_count",
        "source_reservation_count",
        "override_source",
    ]

    return (
        pd.DataFrame(
            summary_rows,
            columns=summary_columns,
        ),
        pd.DataFrame(
            line_rows,
            columns=line_columns,
        ),
    )
