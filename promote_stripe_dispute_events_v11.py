from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src.review.stripe_linked_disputes import (
    apply_linked_dispute_promotion,
    build_linked_dispute_approvals,
    preview_linked_dispute_promotion,
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
        help="Promote explicitly Approved linked disputes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print(
        "DSRL Linked Stripe Disputes - Phase 11E"
    )
    print("=" * 62)

    payment_path = choose_payment_ledger()
    approval_path = (
        CONFIG / "stripe_dispute_approvals_v11.csv"
    )
    preview_path = (
        PROCESSED
        / "stripe_dispute_promotion_preview_v11.csv"
    )
    history_path = (
        CONFIG / "posting_history_manual_seeds.csv"
    )

    try:
        payment_ledger = read_csv(payment_path)
        generated = build_linked_dispute_approvals(
            payment_ledger
        )

        if approval_path.exists():
            approvals = read_csv(approval_path)
        else:
            approvals = generated
            approvals.to_csv(
                approval_path,
                index=False,
            )

        history = read_csv(history_path)

        if args.apply:
            preview, updated_history, updated_approvals = (
                apply_linked_dispute_promotion(
                    approvals=approvals,
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
            preview, _ = (
                preview_linked_dispute_promotion(
                    approvals=approvals,
                    existing_history=history,
                )
            )

        preview.to_csv(
            preview_path,
            index=False,
        )

    except Exception as exc:
        print(
            f"ERROR: Linked dispute workflow failed: {exc}"
        )
        return 1

    print(
        f"Detected dispute groups:     {len(generated):>6}"
    )
    print(
        "Approved groups:            "
        f"{int((approvals['approval_status'] == 'Approved').sum()) if not approvals.empty else 0:>6}"
    )
    print(
        f"Preview groups:             {len(preview):>6}"
    )

    if not approvals.empty:
        print()
        print("Linked dispute approvals")
        print("-" * 62)
        print(
            approvals[
                [
                    "payment_event_id",
                    "source_id",
                    "payout_id",
                    "gross_amount",
                    "processor_fee",
                    "net_amount",
                    "linked_reservation_id",
                    "linked_guest",
                    "approval_status",
                ]
            ].to_string(index=False)
        )

    if not preview.empty:
        print()
        print("Promotion preview")
        print("-" * 62)
        print(
            preview[
                [
                    "payout_id",
                    "linked_guest",
                    "linked_reservation_id",
                    "validation_status",
                    "reversal_total",
                    "dispute_fee",
                    "proposed_total",
                    "net_amount",
                    "lines_to_promote",
                    "validation_detail",
                ]
            ].to_string(index=False)
        )

    print()
    print(f"Approvals: {approval_path}")
    print(f"Preview:   {preview_path}")

    if args.apply:
        print(
            "Approved linked dispute entries were promoted."
        )
    else:
        print(
            "Preview only. Complete the link and mark Approved, "
            "then rerun with --apply."
        )

    print("No QuickBooks transactions were created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
