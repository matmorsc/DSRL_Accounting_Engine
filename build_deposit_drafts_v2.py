from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

from src.posting.payment_allocations import build_payment_allocations
from src.posting.deposit_drafts_v2 import build_deposit_drafts_v2
from src.review.overrides import (
    apply_manual_payment_matches,
    read_manual_payment_matches,
    read_payout_adjustments,
)


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
CONFIG = ROOT / "config" / "deposit_draft_rules.yaml"
PAYMENT_MATCHES = (
    ROOT / "config" / "manual_payment_matches.csv"
)
PAYOUT_ADJUSTMENTS = (
    ROOT / "config" / "payout_adjustments.csv"
)


def read_csv(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run `python run.py` first."
        )
    return pd.read_csv(path)


def main() -> int:
    print("DSRL Payment Allocation + Deposit Draft V2")
    print("=" * 46)

    try:
        with CONFIG.open("r", encoding="utf-8") as handle:
            rules = yaml.safe_load(handle)

        payment_ledger = apply_manual_payment_matches(
            read_csv("payment_ledger.csv"),
            read_manual_payment_matches(PAYMENT_MATCHES),
        )

        allocations, diagnostics = build_payment_allocations(
            payment_ledger=payment_ledger,
            reservations=read_csv("reservations.csv"),
            rules=rules,
        )

        summaries, lines = build_deposit_drafts_v2(
            posting_status=read_csv("posting_status.csv"),
            payout_ledger=read_csv("payout_ledger.csv"),
            allocations=allocations,
            rules=rules,
            payout_adjustments=read_payout_adjustments(
                PAYOUT_ADJUSTMENTS
            ),
        )

        outputs = {
            "payment_ledger_reviewed.csv": payment_ledger,
            "payment_allocations.csv": allocations,
            "payment_allocation_diagnostics.csv": diagnostics,
            "deposit_drafts_v2.csv": summaries,
            "deposit_draft_lines_v2.csv": lines,
        }

        for filename, frame in outputs.items():
            frame.to_csv(PROCESSED / filename, index=False)

    except Exception as exc:
        print(f"ERROR: V2 generation failed: {exc}")
        return 1

    print(f"Payment allocations:          {len(allocations):>6}")
    print(f"Allocation diagnostics:       {len(diagnostics):>6}")
    print(f"Deposit drafts V2:            {len(summaries):>6}")
    print(f"Deposit draft lines V2:       {len(lines):>6}")
    print()

    if not summaries.empty:
        print("Draft status")
        print("-" * 46)
        for status, count in (
            summaries["draft_status"]
            .value_counts(dropna=False)
            .sort_index()
            .items()
        ):
            print(f"{status:<32} {count:>6}")

        print()
        print("Balance check")
        print("-" * 46)
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
