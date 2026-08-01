from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.matching.unlinked_review import (
    build_unlinked_stripe_review,
)


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"


def read_csv(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run `python run.py` first."
        )
    return pd.read_csv(path)


def main() -> int:
    print("DSRL Unlinked Stripe Review")
    print("=" * 40)

    try:
        cognito_path = PROCESSED / "cognito_renewals.csv"
        cognito = (
            pd.read_csv(cognito_path)
            if cognito_path.exists()
            else None
        )

        review = build_unlinked_stripe_review(
            payment_ledger=read_csv("payment_ledger.csv"),
            reservations=read_csv("reservations.csv"),
            cognito_renewals=cognito,
            top_n=5,
        )

        output_path = (
            PROCESSED / "unlinked_stripe_review.csv"
        )
        review.to_csv(output_path, index=False)

    except Exception as exc:
        print(f"ERROR: Review generation failed: {exc}")
        return 1

    print(f"Unlinked Stripe events: {len(review):>6}")
    print(f"Output: {output_path}")
    print()

    if not review.empty:
        strong = (
            pd.to_numeric(
                review["candidate_1_score"],
                errors="coerce",
            )
            .fillna(0)
            .ge(70)
            .sum()
        )
        print(f"Top candidate score >= 70: {strong}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
