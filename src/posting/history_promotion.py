from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.posting.history import (
    POSTING_HISTORY_COLUMNS,
    validate_posting_history,
)


def _text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def promote_approved_posting_history(
    *,
    proposed_history: pd.DataFrame,
    review: pd.DataFrame,
    existing_history: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Append explicitly approved Original posting groups.

    Approval is keyed by posting_group_id because payment_event_id may be
    shared by multiple Airbnb balance events.
    """
    approved_group_ids = set(
        review.loc[
            review["approved_for_promotion"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("yes")
            & review["review_status"]
            .astype(str)
            .str.strip()
            .eq("Ready for Promotion"),
            "posting_group_id",
        ]
        .astype(str)
        .str.strip()
    )

    candidates = proposed_history.loc[
        proposed_history["posting_group_id"]
        .astype(str)
        .str.strip()
        .isin(approved_group_ids)
        & proposed_history["posting_type"]
        .astype(str)
        .str.strip()
        .eq("Original")
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

    promoted["status"] = "Active"

    diagnostics: list[dict[str, object]] = []

    skipped_duplicates = candidates.loc[
        candidates["posting_line_id"]
        .astype(str)
        .str.strip()
        .isin(existing_ids)
    ]

    for _, row in skipped_duplicates.iterrows():
        diagnostics.append(
            {
                "posting_line_id": _text(
                    row.get("posting_line_id")
                ),
                "posting_group_id": _text(
                    row.get("posting_group_id")
                ),
                "payment_event_id": _text(
                    row.get("payment_event_id")
                ),
                "diagnostic_type": (
                    "Already In Posting History"
                ),
                "detail": (
                    "Approved line already existed and was not duplicated."
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


def write_posting_history_atomic(
    frame: pd.DataFrame,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(
        path.suffix + ".tmp"
    )
    frame.to_csv(temp_path, index=False)
    temp_path.replace(path)
