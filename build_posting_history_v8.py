from __future__ import annotations
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd
from src.artifacts import require_fresh_artifact
from src.posting.history import (
    build_proposed_posting_history,
    read_posting_history,
    validate_posting_history,
)

ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
HISTORY_PATH = ROOT / "config" / "posting_history.csv"

def read_csv(name):
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run the current pipeline first.")
    return pd.read_csv(path)

def main():
    print("DSRL Posting History V8 - Phase A")
    print("=" * 44)
    try:
        allocation_file = "payment_allocations_v6.csv"
        ledger_file = "payment_ledger_v6.csv"
        canonical_ledger = PROCESSED / "payment_ledger.csv"
        require_fresh_artifact(
            PROCESSED / allocation_file,
            generated_by="python build_stripe_payout_reconciliation_v6.py",
            newer_than=(canonical_ledger,),
        )
        require_fresh_artifact(
            PROCESSED / ledger_file,
            generated_by="python build_stripe_payout_reconciliation_v6.py",
            newer_than=(canonical_ledger,),
        )
        existing = read_posting_history(HISTORY_PATH)
        validate_posting_history(existing)
        proposed, diagnostics = build_proposed_posting_history(
            allocations=read_csv(allocation_file),
            payment_ledger=read_csv(ledger_file),
            existing_history=existing,
            created_at=datetime.now().replace(microsecond=0).isoformat(),
        )
        proposed_path = PROCESSED / "posting_history_proposed.csv"
        diagnostics_path = PROCESSED / "posting_history_diagnostics.csv"
        proposed.to_csv(proposed_path, index=False)
        diagnostics.to_csv(diagnostics_path, index=False)
    except Exception as exc:
        print(f"ERROR: Posting History Phase A failed: {exc}")
        return 1

    print(f"Allocation source:           {allocation_file}")
    print(f"Payment ledger source:       {ledger_file}")
    print(f"Existing history lines:      {len(existing):>6}")
    print(f"Proposed history lines:      {len(proposed):>6}")
    print(f"Diagnostics:                 {len(diagnostics):>6}")
    print()
    if not proposed.empty:
        print("Posting type")
        print("-" * 44)
        for key, count in proposed["posting_type"].value_counts().sort_index().items():
            print(f"{key:<30} {count:>6}")
    print()
    print(f"Proposed output: {proposed_path}")
    print(f"Diagnostics:     {diagnostics_path}")
    print()
    print("Persistent posting history was not modified.")
    print("No QuickBooks transactions were created.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
