from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent

STAGES = (
    "run.py",
    "build_stripe_payout_reconciliation_v6.py",
    "build_posting_history_v8.py",
    "build_posting_history_reversals_v8.py",
    "build_ledger_deposit_drafts_v9.py",
    "build_posting_package_v10.py",
    "build_quickbooks_posting_package_v10.py",
)


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
