from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.posting.airbnb_adjustments import (
    build_airbnb_adjustment_review,
)


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"


def main() -> int:
    print("DSRL Airbnb Adjustment Review")
    print("=" * 42)

    try:
        proposed_path = (
            PROCESSED / "posting_history_proposed.csv"
        )
        if not proposed_path.exists():
            raise FileNotFoundError(
                "Run build_posting_history_v8.py first."
            )

        proposed = pd.read_csv(proposed_path)
        review = build_airbnb_adjustment_review(
            proposed
        )

        output_path = (
            PROCESSED
            / "airbnb_adjustment_review.csv"
        )
        review.to_csv(output_path, index=False)

    except Exception as exc:
        print(
            f"ERROR: Airbnb adjustment review failed: {exc}"
        )
        return 1

    print(f"Adjustment groups:       {len(review):>6}")
    if not review.empty:
        print()
        print("Review status")
        print("-" * 42)
        print(
            review["review_status"]
            .value_counts()
            .sort_index()
            .to_string()
        )

    print()
    print(f"Review output: {output_path}")
    print("No posting history was modified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
