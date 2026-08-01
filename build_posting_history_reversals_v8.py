from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.posting.history import (
    POSTING_HISTORY_COLUMNS,
    read_posting_history,
    validate_posting_history,
)
from src.posting.history_reversals import (
    build_reversal_preview,
)


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
HISTORY_PATH = ROOT / "config" / "posting_history.csv"
SEEDS_PATH = (
    ROOT / "config" / "posting_history_manual_seeds.csv"
)


def read_csv(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}.")
    return pd.read_csv(path)


def choose_payment_ledger() -> str:
    for name in [
        "payment_ledger_v6.csv",
        "payment_ledger.csv",
    ]:
        if (PROCESSED / name).exists():
            return name
    raise FileNotFoundError("No payment ledger found.")


def read_manual_seeds() -> pd.DataFrame:
    if not SEEDS_PATH.exists():
        return pd.DataFrame(
            columns=POSTING_HISTORY_COLUMNS
        )

    seeds = pd.read_csv(
        SEEDS_PATH,
        dtype=str,
        keep_default_na=False,
    )

    missing = [
        column
        for column in POSTING_HISTORY_COLUMNS
        if column not in seeds.columns
    ]
    if missing:
        raise ValueError(
            f"{SEEDS_PATH.name} missing columns: {missing}"
        )

    active = seeds.loc[
        seeds["status"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("active")
    ].copy()

    return active[POSTING_HISTORY_COLUMNS]


def main() -> int:
    print(
        "DSRL Posting History V8 - Phase C Reversal Preview"
    )
    print("=" * 56)

    try:
        ledger_file = choose_payment_ledger()
        history = read_posting_history(
            HISTORY_PATH
        )
        seeds = read_manual_seeds()

        combined_history = pd.concat(
            [history, seeds],
            ignore_index=True,
        )
        validate_posting_history(
            combined_history
        )

        reversals, review = build_reversal_preview(
            payment_ledger=read_csv(
                ledger_file
            ),
            posting_history=combined_history,
            created_at=datetime.now().replace(
                microsecond=0
            ).isoformat(),
        )

        reversal_path = (
            PROCESSED
            / "posting_history_reversal_preview.csv"
        )
        review_path = (
            PROCESSED
            / "posting_history_reversal_review.csv"
        )

        reversals.to_csv(
            reversal_path,
            index=False,
        )
        review.to_csv(
            review_path,
            index=False,
        )

    except Exception as exc:
        print(
            f"ERROR: Phase C reversal preview failed: "
            f"{exc}"
        )
        return 1

    print(f"Payment ledger source:       {ledger_file}")
    print(f"Persistent history lines:    {len(history):>6}")
    print(f"Active manual seed lines:    {len(seeds):>6}")
    print(f"Combined history lines:      {len(combined_history):>6}")
    print(f"Proposed reversal lines:     {len(reversals):>6}")
    print(f"Source events needing review:{len(review):>6}")
    print()

    if not reversals.empty:
        event_summary = (
            reversals.groupby(
                [
                    "payment_event_id",
                    "transaction_type",
                    "source_id",
                    "payout_id",
                ],
                dropna=False,
            )
            .agg(
                reversal_lines=(
                    "posting_line_id",
                    "count",
                ),
                reversal_total=(
                    "signed_amount",
                    lambda values: round(
                        pd.to_numeric(
                            values,
                            errors="coerce",
                        )
                        .fillna(0.0)
                        .sum(),
                        2,
                    ),
                ),
            )
            .reset_index()
        )

        print("Reversal event summary")
        print("-" * 56)
        print(event_summary.to_string(index=False))
        print()

    target_source = "ch_3ToU7JJtejknM7351lfydf5x"
    target = reversals.loc[
        reversals["source_id"]
        .astype(str)
        .eq(target_source)
    ]

    print("Dan Calabro acceptance test")
    print("-" * 56)

    if target.empty:
        print("No reversal lines generated.")
    else:
        target_total = round(
            pd.to_numeric(
                target["signed_amount"],
                errors="coerce",
            )
            .fillna(0.0)
            .sum(),
            2,
        )
        print(f"Reversal lines: {len(target)}")
        print(f"Net reversal:   {target_total:.2f}")
        print(
            f"Balanced target: "
            f"{'Yes' if target_total == -54.32 else 'No'}"
        )

    print()
    if not review.empty:
        print("Review status")
        print("-" * 56)
        for status, count in (
            review["review_status"]
            .value_counts()
            .sort_index()
            .items()
        ):
            print(f"{status:<38} {count:>6}")
        print()

    print(f"Reversal preview: {reversal_path}")
    print(f"Review queue:     {review_path}")
    print()
    print(
        "Persistent posting history was not modified."
    )
    print("No QuickBooks transactions were created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
