from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src.review.original_charge_reconstruction import (
    apply_reconstruction_promotion,
    build_reconstruction_candidates,
    preview_reconstruction_promotion,
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


def choose_file(names: list[str]) -> Path:
    for name in names:
        path = PROCESSED / name
        if path.exists():
            return path
    raise FileNotFoundError(
        "Required processed file not found: "
        + ", ".join(names)
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Promote explicitly Approved reconstruction groups.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print(
        "DSRL Evidence-Based Original Charge Reconstruction - Phase 11F"
    )
    print("=" * 76)

    payment_path = choose_file(
        ["payment_ledger_v6.csv", "payment_ledger.csv"]
    )
    reservations_path = choose_file(["reservations.csv"])
    tax_path = CONFIG / "tax_rates_v11.csv"
    approval_path = (
        CONFIG
        / "original_charge_reconstruction_approvals_v11.csv"
    )
    preview_path = (
        PROCESSED
        / "original_charge_reconstruction_preview_v11.csv"
    )
    history_path = (
        CONFIG / "posting_history_manual_seeds.csv"
    )

    try:
        payment_ledger = read_csv(payment_path)
        reservations = read_csv(reservations_path)
        tax_config = read_csv(tax_path)

        generated = build_reconstruction_candidates(
            payment_ledger=payment_ledger,
            reservations=reservations,
            tax_config=tax_config,
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
                apply_reconstruction_promotion(
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
            preview, _ = preview_reconstruction_promotion(
                approvals=approvals,
                existing_history=history,
            )

        preview.to_csv(
            preview_path,
            index=False,
        )

    except Exception as exc:
        print(
            f"ERROR: Original charge reconstruction failed: {exc}"
        )
        return 1

    print(
        f"Candidate groups detected:  {len(generated):>6}"
    )
    print(
        "Approval eligible groups:  "
        f"{int((generated['approval_eligible'] == 'Yes').sum()) if not generated.empty else 0:>6}"
    )
    print(
        "Approved groups:           "
        f"{int((approvals['approval_status'] == 'Approved').sum()) if not approvals.empty else 0:>6}"
    )
    print(
        f"Preview groups:             {len(preview):>6}"
    )

    if not generated.empty:
        print()
        print("Reconstruction candidates")
        print("-" * 76)
        print(
            generated[
                [
                    "payout_id",
                    "guest",
                    "listing",
                    "gross_amount",
                    "reconstructed_revenue",
                    "reconstructed_state_tax",
                    "reconstructed_local_tax",
                    "processor_fee",
                    "net_amount",
                    "approval_eligible",
                    "approval_status",
                ]
            ].to_string(index=False)
        )

    if not preview.empty:
        print()
        print("Promotion preview")
        print("-" * 76)
        print(
            preview[
                [
                    "payout_id",
                    "guest",
                    "listing",
                    "validation_status",
                    "proposed_net",
                    "expected_net",
                    "lines_to_promote",
                    "validation_detail",
                ]
            ].to_string(index=False)
        )

    print()
    print(f"Tax config: {tax_path}")
    print(f"Approvals:  {approval_path}")
    print(f"Preview:    {preview_path}")

    if args.apply:
        print(
            "Approved reconstruction entries were promoted."
        )
    else:
        print(
            "Preview only. Mark intended eligible rows Approved, "
            "then rerun with --apply."
        )

    print("No QuickBooks transactions were created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
