from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.presentation.posting_package import build_posting_package


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"


def read_csv(name):
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}.")
    return pd.read_csv(path)


def choose_file(candidates, label):
    for name in candidates:
        if (PROCESSED / name).exists():
            return name
    raise FileNotFoundError(f"No {label} file found.")


def main():
    print("DSRL Posting Package V10 - Phase 10A.1")
    print("=" * 50)

    try:
        payout_file = choose_file(
            ["payout_ledger_v6.csv", "payout_ledger.csv"],
            "payout ledger",
        )
        bank_file = choose_file(
            ["bank_transactions.csv"],
            "bank transactions",
        )

        summary, lines = build_posting_package(
            deposit_drafts=read_csv("deposit_drafts_v9.csv"),
            deposit_lines=read_csv("deposit_draft_lines_v9.csv"),
            comparison=read_csv("deposit_draft_comparison_v9.csv"),
            payout_ledger=read_csv(payout_file),
            bank_transactions=read_csv(bank_file),
        )

        summary_path = PROCESSED / "posting_package_summary_v10.csv"
        lines_path = PROCESSED / "posting_package_v10.csv"
        summary.to_csv(summary_path, index=False)
        lines.to_csv(lines_path, index=False)

    except Exception as exc:
        print(f"ERROR: Posting Package Phase 10A.1 failed: {exc}")
        return 1

    print(f"Payout ledger source:        {payout_file}")
    print(f"Bank transaction source:     {bank_file}")
    print(f"Posting packages:            {len(summary):>6}")
    print(f"Posting package lines:       {len(lines):>6}")
    print()
    print("Bank balance status")
    print("-" * 50)
    print(summary["bank_balanced"].value_counts(dropna=False).sort_index().to_string())
    print()
    print("Confidence")
    print("-" * 50)
    print(summary["confidence"].value_counts(dropna=False).sort_index().to_string())

    target = "po_1TqjcpJtejknM735RBYtfOau"
    target_row = summary.loc[summary["payout_id"].astype(str).eq(target)]

    print()
    print("Dan Calabro package acceptance test")
    print("-" * 50)
    if target_row.empty:
        print("Target payout not found.")
    else:
        row = target_row.iloc[0]
        for label, field in [
            ("Processor payout date", "processor_payout_date"),
            ("Bank transaction date", "bank_transaction_date"),
            ("Bank description", "bank_description"),
            ("Bank amount", "bank_amount"),
            ("Posting total", "posting_total"),
            ("Bank difference", "bank_difference"),
            ("Bank balanced", "bank_balanced"),
            ("Confidence", "confidence"),
            ("Sheet name", "sheet_name"),
            ("Bank feed label", "bank_feed_label"),
        ]:
            print(f"{label:<24} {row[field]}")

    print()
    print(f"Summary output: {summary_path}")
    print(f"Line output:    {lines_path}")
    print()
    print("No workbook was created yet.")
    print("No posting history was modified.")
    print("No QuickBooks transactions were created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
