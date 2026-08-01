from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.posting.history_review import (
    build_posting_history_review,
)


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"


def read_csv(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run Phase A first."
        )
    return pd.read_csv(path)


def choose_payment_ledger() -> str:
    for name in [
        "payment_ledger_v6.csv",
        "payment_ledger.csv",
    ]:
        if (PROCESSED / name).exists():
            return name
    raise FileNotFoundError(
        "No payment ledger file found."
    )


def main() -> int:
    print("DSRL Posting History V8 - Phase B Review")
    print("=" * 48)

    try:
        ledger_file = choose_payment_ledger()

        review = build_posting_history_review(
            proposed_history=read_csv(
                "posting_history_proposed.csv"
            ),
            payment_ledger=read_csv(
                ledger_file
            ),
            tolerance=0.02,
        )

        output_path = (
            PROCESSED / "posting_history_review.csv"
        )
        review.to_csv(output_path, index=False)

    except Exception as exc:
        print(
            f"ERROR: Posting history review failed: "
            f"{exc}"
        )
        return 1

    print(f"Payment ledger source:     {ledger_file}")
    print(f"Review events:             {len(review):>6}")
    print()

    print("Review status")
    print("-" * 48)
    for status, count in (
        review["review_status"]
        .value_counts(dropna=False)
        .sort_index()
        .items()
    ):
        print(f"{status:<32} {count:>6}")

    print()
    print(f"Review output: {output_path}")
    print()
    print(
        "No posting history was promoted."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
