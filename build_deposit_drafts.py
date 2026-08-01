from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

from src.posting.deposit_drafts import build_deposit_drafts


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
CONFIG = ROOT / "config" / "deposit_draft_rules.yaml"


def read_csv(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run `python run.py` first."
        )
    return pd.read_csv(path)


def main() -> int:
    print("DSRL Deposit Draft Generator")
    print("=" * 40)

    if not CONFIG.exists():
        print(f"ERROR: Missing configuration file:\n{CONFIG}")
        return 1

    try:
        with CONFIG.open("r", encoding="utf-8") as handle:
            rules = yaml.safe_load(handle)

        summaries, lines = build_deposit_drafts(
            posting_status=read_csv("posting_status.csv"),
            payout_ledger=read_csv("payout_ledger.csv"),
            payment_ledger=read_csv("payment_ledger.csv"),
            reservations=read_csv("reservations.csv"),
            rules=rules,
        )

        summary_path = PROCESSED / "deposit_drafts.csv"
        lines_path = PROCESSED / "deposit_draft_lines.csv"

        summaries.to_csv(summary_path, index=False)
        lines.to_csv(lines_path, index=False)

    except Exception as exc:
        print(f"ERROR: Deposit draft generation failed: {exc}")
        return 1

    print(f"Deposit drafts:       {len(summaries):>6}  {summary_path.name}")
    print(f"Deposit draft lines:  {len(lines):>6}  {lines_path.name}")
    print()

    print("Draft status")
    print("-" * 40)
    if summaries.empty:
        print("No payouts are currently eligible for draft generation.")
    else:
        for status, count in (
            summaries["draft_status"]
            .value_counts(dropna=False)
            .sort_index()
            .items()
        ):
            print(f"{status:<30} {count:>6}")

        print()
        print("Balance check")
        print("-" * 40)
        print(
            summaries["balanced"]
            .value_counts(dropna=False)
            .sort_index()
            .to_string()
        )

    print()
    print("No QuickBooks transactions were created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
