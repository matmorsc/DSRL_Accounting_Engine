from __future__ import annotations

import pandas as pd

from src.posting.history import (
    POSTING_HISTORY_COLUMNS,
    validate_posting_history,
)


AIRBNB_ADJUSTMENT_EVENT_TYPES = {
    "adjustment",
    "resolution adjustment",
    "cancellation fee",
}


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


def build_airbnb_adjustment_review(
    proposed_history: pd.DataFrame,
) -> pd.DataFrame:
    candidates = proposed_history.loc[
        proposed_history["processor"]
        .astype(str)
        .str.strip()
        .eq("Airbnb")
        & proposed_history["posting_type"]
        .astype(str)
        .str.strip()
        .eq("Source Event")
        & proposed_history["transaction_type"]
        .astype(str)
        .str.lower()
        .str.strip()
        .isin(AIRBNB_ADJUSTMENT_EVENT_TYPES)
    ].copy()

    rows: list[dict[str, object]] = []

    for posting_group_id, group in candidates.groupby(
        "posting_group_id",
        dropna=False,
        sort=True,
    ):
        missing_account = int(
            group["account"].astype(str).str.strip().eq("").sum()
        )
        missing_class = int(
            group["class"].astype(str).str.strip().eq("").sum()
        )
        missing_payout = int(
            group["payout_id"].astype(str).str.strip().eq("").sum()
        )
        total = round(
            pd.to_numeric(
                group["signed_amount"],
                errors="coerce",
            ).fillna(0.0).sum(),
            2,
        )

        reasons: list[str] = []
        if missing_account:
            reasons.append(
                f"{missing_account} line(s) missing account."
            )
        if missing_class:
            reasons.append(
                f"{missing_class} line(s) missing class."
            )
        if missing_payout:
            reasons.append(
                f"{missing_payout} line(s) missing payout ID."
            )
        if abs(total) < 0.005:
            reasons.append(
                "Adjustment group total is zero."
            )

        status = (
            "Ready for Promotion"
            if not reasons
            else "Review Required"
        )

        first = group.iloc[0]

        rows.append(
            {
                "posting_group_id": _text(posting_group_id),
                "payment_event_id": _text(
                    first.get("payment_event_id")
                ),
                "processor": "Airbnb",
                "transaction_type": _text(
                    first.get("transaction_type")
                ).lower(),
                "transaction_date": _text(
                    first.get("transaction_date")
                ),
                "source_id": _text(
                    first.get("source_id")
                ),
                "payout_id": _text(
                    first.get("payout_id")
                ),
                "account": _text(
                    first.get("account")
                ),
                "class": _text(
                    first.get("class")
                ),
                "description": _text(
                    first.get("description")
                ),
                "line_count": len(group),
                "adjustment_total": total,
                "review_status": status,
                "review_reason": " ".join(reasons),
                "approved_for_promotion": (
                    "Pending"
                    if status == "Ready for Promotion"
                    else "No"
                ),
                "review_notes": "",
            }
        )

    columns = [
        "posting_group_id",
        "payment_event_id",
        "processor",
        "transaction_type",
        "transaction_date",
        "source_id",
        "payout_id",
        "account",
        "class",
        "description",
        "line_count",
        "adjustment_total",
        "review_status",
        "review_reason",
        "approved_for_promotion",
        "review_notes",
    ]

    return pd.DataFrame(rows, columns=columns)


def promote_airbnb_adjustments(
    *,
    proposed_history: pd.DataFrame,
    review: pd.DataFrame,
    existing_history: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    approved_groups = set(
        review.loc[
            review["review_status"]
            .astype(str)
            .str.strip()
            .eq("Ready for Promotion")
            & review["approved_for_promotion"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("yes"),
            "posting_group_id",
        ]
        .astype(str)
        .str.strip()
    )

    candidates = proposed_history.loc[
        proposed_history["posting_group_id"]
        .astype(str)
        .str.strip()
        .isin(approved_groups)
        & proposed_history["processor"]
        .astype(str)
        .str.strip()
        .eq("Airbnb")
        & proposed_history["posting_type"]
        .astype(str)
        .str.strip()
        .eq("Source Event")
        & proposed_history["transaction_type"]
        .astype(str)
        .str.lower()
        .str.strip()
        .isin(AIRBNB_ADJUSTMENT_EVENT_TYPES)
    ].copy()

    existing_ids = set(
        existing_history["posting_line_id"]
        .astype(str)
        .str.strip()
    )

    promoted = candidates.loc[
        ~candidates["posting_line_id"]
        .astype(str)
        .str.strip()
        .isin(existing_ids)
    ].copy()

    promoted["posting_type"] = "Adjustment"
    promoted["status"] = "Active"
    promoted["classification_source"] = (
        "Approved standalone Airbnb adjustment"
    )

    diagnostics: list[dict[str, object]] = []

    duplicate_rows = candidates.loc[
        candidates["posting_line_id"]
        .astype(str)
        .str.strip()
        .isin(existing_ids)
    ]

    for _, row in duplicate_rows.iterrows():
        diagnostics.append(
            {
                "posting_line_id": _text(
                    row.get("posting_line_id")
                ),
                "posting_group_id": _text(
                    row.get("posting_group_id")
                ),
                "diagnostic_type": (
                    "Already In Posting History"
                ),
                "detail": (
                    "Adjustment line already existed and was not duplicated."
                ),
            }
        )

    combined = pd.concat(
        [
            existing_history[POSTING_HISTORY_COLUMNS],
            promoted[POSTING_HISTORY_COLUMNS],
        ],
        ignore_index=True,
    )

    validate_posting_history(combined)

    return combined, pd.DataFrame(diagnostics)