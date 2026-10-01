from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
REVIEW_PATH = (
    ROOT / "data" / "processed" / "posting_history_review.csv"
)

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


def check_posting_history_promotion_gate() -> int:
    if not REVIEW_PATH.exists():
        print()
        print(
            "ERROR: Posting-history review stage completed without creating "
            f"{REVIEW_PATH}."
        )
        print(
            "Month-end build stopped before reversals and V9 deposits."
        )
        return 1

    review = pd.read_csv(REVIEW_PATH)

    missing_columns = [
        column
        for column in (
            "review_status",
            "approved_for_promotion",
        )
        if column not in review.columns
    ]
    if missing_columns:
        print()
        print(
            "ERROR: Posting-history review file is missing required "
            f"columns: {missing_columns}"
        )
        print(
            "Month-end build stopped before reversals and V9 deposits."
        )
        return 1

    ready_for_promotion = (
        review["review_status"]
        .astype(str)
        .str.strip()
        .eq("Ready for Promotion")
    )
    approved_for_promotion = (
        review["approved_for_promotion"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("yes")
    )
    pending_promotion_count = int(
        (ready_for_promotion & ~approved_for_promotion).sum()
    )

    if pending_promotion_count == 0:
        return 0

    print()
    print("!" * 72)
    print("MONTH-END STOP: POSTING HISTORY PROMOTION REQUIRED")
    print("!" * 72)
    print(
        f"Payment events requiring promotion approval: {pending_promotion_count}"
    )
    print(f"Review file: {REVIEW_PATH}")
    print(
        "Approve only rows where review_status is Ready for Promotion."
    )
    print(
        "Do not approve Review Required or Excluded - Source Event rows."
    )
    print("Run: python promote_posting_history_v8.py")
    print("Then rerun: python build_month_end_package.py")
    return 1


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
            gate_result = check_posting_history_promotion_gate()
            if gate_result:
                return gate_result

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
