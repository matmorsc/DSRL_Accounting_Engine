from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src.review.refunded_stripe_families import (
    apply_refunded_family_promotion,
    build_refunded_family_candidates,
    preview_refunded_family_promotion,
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
        help=(
            "Promote explicitly Approved "
            "fully refunded Stripe families."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print(
        "DSRL Fully Refunded Stripe Families - Phase 11H"
    )
    print("=" * 72)

    payment_path = choose_file(
        [
            "payment_ledger_v6.csv",
            "payment_ledger.csv",
        ]
    )
    reservations_path = choose_file(
        ["reservations.csv"]
    )
    approval_path = (
        CONFIG
        / "refunded_stripe_family_approvals_v11.csv"
    )
    preview_path = (
        PROCESSED
        / "refunded_stripe_family_preview_v11.csv"
    )
    history_path = (
        CONFIG
        / "posting_history_manual_seeds.csv"
    )

    try:
        payment_ledger = read_csv(
            payment_path
        )
        reservations = read_csv(
            reservations_path
        )
        generated = (
            build_refunded_family_candidates(
                payment_ledger=payment_ledger,
                reservations=reservations,
            )
        )

        if approval_path.exists():
            approvals = read_csv(
                approval_path
            )
        else:
            approvals = generated
            approvals.to_csv(
                approval_path,
                index=False,
            )

        history = read_csv(
            history_path
        )

        if args.apply:
            (
                preview,
                updated_history,
                updated_approvals,
            ) = apply_refunded_family_promotion(
                approvals=approvals,
                existing_history=history,
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
                preview_refunded_family_promotion(
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
            "ERROR: Refunded Stripe family workflow "
            f"failed: {exc}"
        )
        return 1

    eligible = (
        int(
            generated["approval_eligible"]
            .astype(str)
            .eq("Yes")
            .sum()
        )
        if not generated.empty
        else 0
    )
    approved = (
        int(
            approvals["approval_status"]
            .astype(str)
            .eq("Approved")
            .sum()
        )
        if not approvals.empty
        else 0
    )

    print(
        f"Candidate families detected: {len(generated):>6}"
    )
    print(
        f"Approval eligible families: {eligible:>6}"
    )
    print(
        f"Approved families:          {approved:>6}"
    )
    print(
        f"Preview families:           {len(preview):>6}"
    )

    if not generated.empty:
        print()
        print("Refunded-family candidates")
        print("-" * 72)
        print(
            generated[
                [
                    "payout_id",
                    "guest",
                    "listing",
                    "processor_fee",
                    "refund_total",
                    "adjustment_total",
                    "family_net",
                    "approval_eligible",
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
                    "payout_id",
                    "guest",
                    "listing",
                    "validation_status",
                    "processor_fee",
                    "adjustment_total",
                    "family_net",
                    "proposed_total",
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
            "Approved refunded-family source events "
            "were promoted."
        )
    else:
        print(
            "Preview only. Approve only the intended "
            "fully refunded family, then rerun with --apply."
        )

    print(
        "No QuickBooks transactions were created."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
