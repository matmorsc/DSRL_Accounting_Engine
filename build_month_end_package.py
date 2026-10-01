from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent

STAGES = (
    "run.py",
    "build_stripe_payout_reconciliation_v6.py",
    "build_posting_history_v8.py",
    "build_posting_history_review.py",
    "build_posting_history_reversals_v8.py",
    "build_ledger_deposit_drafts_v9.py",
    "build_posting_package_v10.py",
    "build_quickbooks_posting_package_v10.py",
)

REVIEW_PATH = ROOT / "data" / "processed" / "posting_history_review.csv"


def check_promotion_gate() -> int:
    review = pd.read_csv(REVIEW_PATH)
    ready = review["review_status"].astype(str).str.strip().eq(
        "Ready for Promotion"
    )
    pending = (
        review["approved_for_promotion"]
        .astype(str)
        .str.strip()
        .str.lower()
        .ne("yes")
    )
    blocked = ready & pending

    if not blocked.any():
        return 0

    print()
    print("!" * 72)
    print("MONTH-END STOP: POSTING HISTORY PROMOTION REQUIRED")
    print("!" * 72)
    print(
        f"{int(blocked.sum())} payment events are Ready for Promotion "
        "but have not been approved."
    )
    print()
    print("Do not continue to the deposit/package stages yet.")
    print("Review:")
    print("  data/processed/posting_history_review.csv")
    print()
    print("Approve only rows with:")
    print("  review_status = Ready for Promotion")
    print()
    print("Then run:")
    print("  python promote_posting_history_v8.py")
    print()
    print("After promotion, rerun:")
    print("  python build_month_end_package.py")
    print("!" * 72)
    return 2


def main() -> int:
    print("DSRL Month-End Posting Package")
    print("=" * 48)

    for stage in STAGES:
        print()
        print(f"Running {stage}")
        print("-" * 48)
        completed = subprocess.run(
            [sys.executable, str(ROOT / stage)],
            cwd=ROOT,
            check=False,
        )
        if completed.returncode:
            print()
            print(f"ERROR: {stage} failed; month-end build stopped.")
            return completed.returncode

        if stage == "build_posting_history_review.py":
            gate = check_promotion_gate()
            if gate:
                return gate

    print()
    print("Month-end posting package build completed.")
    print("No QuickBooks transactions were created.")
    print()
    print("!" * 72)
    print("WARNING: Generating the workbook does not mark its payouts as posted.")
    print(
        "After entering entries in QuickBooks, refresh the QuickBooks exports"
    )
    print(
        "before the next month-end run, or record an appropriate Already Posted"
    )
    print("manual override. Otherwise, those payouts may be proposed again.")
    print("!" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
