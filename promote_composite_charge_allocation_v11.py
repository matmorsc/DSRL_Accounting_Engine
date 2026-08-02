from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src.review.composite_charge_allocation import (
    apply_composite_promotion,
    preview_composite_promotion,
)


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
CONFIG = ROOT / "config"


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
    )


def choose_payment_ledger() -> Path:
    for name in [
        "payment_ledger_v6.csv",
        "payment_ledger.csv",
    ]:
        path = PROCESSED / name
        if path.exists():
            return path
    raise FileNotFoundError(
        "No payment ledger file found."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Promote explicitly Approved composite groups.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print(
        "DSRL Composite Charge Allocation - Phase 11G"
    )
    print("=" * 72)

    payment_path = choose_payment_ledger()
    allocation_path = (
        CONFIG / "composite_charge_allocations_v11.csv"
    )
    approval_path = (
        CONFIG / "composite_charge_approvals_v11.csv"
    )
    preview_path = (
        PROCESSED
        / "composite_charge_promotion_preview_v11.csv"
    )
    history_path = (
        CONFIG / "posting_history_manual_seeds.csv"
    )

    try:
        payment_ledger = read_csv(payment_path)
        allocations = read_csv(allocation_path)
        approvals = read_csv(approval_path)
        history = read_csv(history_path)

        if args.apply:
            preview, updated_history, updated_approvals = (
                apply_composite_promotion(
                    approvals=approvals,
                    allocations=allocations,
                    payment_ledger=payment_ledger,
                    existing_history=history,
                )
            )
            updated_history.to_csv(
                history_path,
                index=False,
            )
            updated_approvals.to_csv(
                approval_path,
                index=False,
            )
        else:
            preview, _ = preview_composite_promotion(
                approvals=approvals,
                allocations=allocations,
                payment_ledger=payment_ledger,
                existing_history=history,
            )

        preview.to_csv(
            preview_path,
            index=False,
        )

    except Exception as exc:
        print(
            f"ERROR: Composite charge workflow failed: {exc}"
        )
        return 1

    approved_count = int(
        approvals["approval_status"]
        .astype(str)
        .str.strip()
        .eq("Approved")
        .sum()
    ) if not approvals.empty else 0

    print(
        f"Composite groups configured: {len(approvals):>6}"
    )
    print(
        f"Approved groups:             {approved_count:>6}"
    )
    print(
        f"Preview groups:              {len(preview):>6}"
    )

    if not approvals.empty:
        print()
        print("Composite approvals")
        print("-" * 72)
        print(
            approvals[
                [
                    "group_name",
                    "payment_event_id",
                    "payout_id",
                    "gross_amount",
                    "processor_fee",
                    "net_amount",
                    "allocation_line_count",
                    "approval_status",
                ]
            ].to_string(index=False)
        )

    if not preview.empty:
        print()
        print("Promotion preview")
        print("-" * 72)
        print(
            preview[
                [
                    "group_name",
                    "payout_id",
                    "validation_status",
                    "allocation_line_count",
                    "allocation_total",
                    "net_amount",
                    "lines_to_promote",
                    "validation_detail",
                ]
            ].to_string(index=False)
        )

    print()
    print(f"Allocations: {allocation_path}")
    print(f"Approvals:   {approval_path}")
    print(f"Preview:     {preview_path}")

    if args.apply:
        print(
            "Approved composite allocation entries were promoted."
        )
    else:
        print(
            "Preview only. Mark the intended group Approved, "
            "then rerun with --apply."
        )

    print("No QuickBooks transactions were created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
