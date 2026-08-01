from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.reports.deposit_exceptions import (
    build_deposit_exception_review,
)


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"


def read_csv(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run the required pipeline first."
        )
    return pd.read_csv(path)


def main() -> int:
    print("DSRL Deposit Exception Review")
    print("=" * 40)

    try:
        review = build_deposit_exception_review(
            deposit_drafts=read_csv(
                "deposit_drafts_v2.csv"
            ),
            draft_lines=read_csv(
                "deposit_draft_lines_v2.csv"
            ),
            allocation_diagnostics=read_csv(
                "payment_allocation_diagnostics.csv"
            ),
            payout_ledger=read_csv("payout_ledger.csv"),
            payment_ledger=read_csv("payment_ledger.csv"),
        )

        output_path = (
            PROCESSED / "deposit_exception_review.csv"
        )
        review.to_csv(output_path, index=False)

    except Exception as exc:
        print(f"ERROR: Exception review failed: {exc}")
        return 1

    print(f"Exception payouts: {len(review):>6}")
    print(f"Output: {output_path}")
    print()

    if not review.empty:
        print("Exception categories")
        print("-" * 40)
        for issue, count in (
            review["primary_issue"]
            .value_counts()
            .sort_index()
            .items()
        ):
            print(f"{issue:<30} {count:>6}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
