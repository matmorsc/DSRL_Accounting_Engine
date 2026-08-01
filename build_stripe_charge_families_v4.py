from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

from src.reconciliation.stripe_charge_families import (
    apply_family_metadata_to_payment_ledger,
    build_stripe_charge_families,
    summarize_stripe_charge_families,
)
from src.reconciliation.stripe_family_assignment import (
    assign_stripe_families_to_payouts,
)
from src.reconciliation.payouts import (
    build_payment_ledger,
    build_payout_ledger,
    summarize_payout_allocations,
    match_payouts_to_bank,
)
from src.posting.engine import build_posting_status
from src.posting.payment_allocations import (
    build_payment_allocations,
)
from src.posting.deposit_drafts_v2 import (
    build_deposit_drafts_v2,
)
from src.review.overrides import read_payout_adjustments


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
SETTINGS = ROOT / "config" / "settings.yaml"
DRAFT_RULES = ROOT / "config" / "deposit_draft_rules.yaml"
POSTING_OVERRIDES = ROOT / "config" / "posting_overrides.csv"
PAYOUT_ADJUSTMENTS = ROOT / "config" / "payout_adjustments.csv"


def read_csv(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run `python run.py` first."
        )
    return pd.read_csv(path)


def main() -> int:
    print("DSRL Stripe Charge-Family Pipeline V4")
    print("=" * 46)

    try:
        with SETTINGS.open("r", encoding="utf-8") as handle:
            settings = yaml.safe_load(handle)

        with DRAFT_RULES.open("r", encoding="utf-8") as handle:
            draft_rules = yaml.safe_load(handle)

        processor_transactions = read_csv(
            "processor_transactions.csv"
        )

        family_transactions, family_diagnostics = (
            build_stripe_charge_families(
                processor_transactions
            )
        )
        family_summary = (
            summarize_stripe_charge_families(
                family_transactions
            )
        )

        payment_ledger = build_payment_ledger(
            family_transactions
        )

        family_columns = [
            "transaction_id",
            "charge_family_id",
            "family_reservation_id",
            "family_channel_reservation_id",
            "family_guest",
            "family_listing",
            "family_metadata_inherited",
        ]

        payment_ledger = payment_ledger.merge(
            family_transactions[family_columns],
            on="transaction_id",
            how="left",
        )
        payment_ledger = apply_family_metadata_to_payment_ledger(
            payment_ledger
        )

        payout_ledger = build_payout_ledger(
            family_transactions
        )

        payment_ledger = assign_stripe_families_to_payouts(
            payment_ledger,
            payout_ledger,
        )

        # Non-Stripe rows keep their existing V3 assignment logic by copying
        # assignments from the current primary payment ledger.
        current_payment_ledger = read_csv("payment_ledger.csv")
        current_lookup = current_payment_ledger[
            [
                "payment_event_id",
                "payout_id",
                "payout_assignment_status",
                "payout_assignment_method",
                "payout_date",
            ]
        ]

        non_stripe_mask = (
            payment_ledger["processor"]
            .astype(str)
            .str.strip()
            .ne("Stripe")
        )

        merged = payment_ledger.loc[
            non_stripe_mask
        ].drop(
            columns=[
                "payout_id",
                "payout_assignment_status",
                "payout_assignment_method",
                "payout_date",
            ],
            errors="ignore",
        ).merge(
            current_lookup,
            on="payment_event_id",
            how="left",
        )

        payment_ledger = pd.concat(
            [
                payment_ledger.loc[~non_stripe_mask],
                merged,
            ],
            ignore_index=True,
            sort=False,
        )

        payout_ledger = summarize_payout_allocations(
            payment_ledger,
            payout_ledger,
        )
        payout_ledger = match_payouts_to_bank(
            payout_ledger,
            read_csv("bank_transactions.csv"),
            date_tolerance_days=int(
                settings["matching"][
                    "bank_date_tolerance_days"
                ]
            ),
            amount_tolerance=float(
                settings["matching"]["amount_tolerance"]
            ),
        )

        posting_status = build_posting_status(
            payout_ledger=payout_ledger,
            quickbooks_gl=read_csv("quickbooks_gl.csv"),
            quickbooks_batches=read_csv(
                "quickbooks_posting_batches.csv"
            ),
            posting_overrides_path=POSTING_OVERRIDES,
            assume_posted_through=settings[
                "quickbooks"
            ]["assume_posted_through"],
            date_tolerance_days=int(
                settings["quickbooks"][
                    "posting_date_tolerance_days"
                ]
            ),
            amount_tolerance=float(
                settings["quickbooks"][
                    "amount_tolerance"
                ]
            ),
        )

        allocations, allocation_diagnostics = (
            build_payment_allocations(
                payment_ledger=payment_ledger,
                reservations=read_csv("reservations.csv"),
                rules=draft_rules,
            )
        )

        drafts, draft_lines = build_deposit_drafts_v2(
            posting_status=posting_status,
            payout_ledger=payout_ledger,
            allocations=allocations,
            rules=draft_rules,
            payout_adjustments=read_payout_adjustments(
                PAYOUT_ADJUSTMENTS
            ),
        )

        outputs = {
            "processor_transactions_v4.csv": family_transactions,
            "stripe_charge_families.csv": family_summary,
            "stripe_charge_family_diagnostics.csv": family_diagnostics,
            "payment_ledger_v4.csv": payment_ledger,
            "payout_ledger_v4.csv": payout_ledger,
            "posting_status_v4.csv": posting_status,
            "payment_allocations_v4.csv": allocations,
            "payment_allocation_diagnostics_v4.csv": allocation_diagnostics,
            "deposit_drafts_v4.csv": drafts,
            "deposit_draft_lines_v4.csv": draft_lines,
        }

        for filename, frame in outputs.items():
            frame.to_csv(PROCESSED / filename, index=False)

    except Exception as exc:
        print(f"ERROR: Stripe Charge-Family V4 failed: {exc}")
        return 1

    print(f"Stripe charge families:       {len(family_summary):>6}")
    print(f"Family diagnostics:           {len(family_diagnostics):>6}")
    print(f"Deposit drafts V4:            {len(drafts):>6}")
    print(f"Deposit draft lines V4:       {len(draft_lines):>6}")
    print()

    print("Draft status")
    print("-" * 46)
    for status, count in (
        drafts["draft_status"]
        .value_counts(dropna=False)
        .sort_index()
        .items()
    ):
        print(f"{status:<32} {count:>6}")

    print()
    print("Balance check")
    print("-" * 46)
    print(
        drafts["balanced"]
        .value_counts(dropna=False)
        .sort_index()
        .to_string()
    )

    print()
    target = "po_1TqjcpJtejknM735RBYtfOau"
    target_row = drafts.loc[
        drafts["payout_id"].astype(str).eq(target)
    ]

    if not target_row.empty:
        row = target_row.iloc[0]
        print()
        print("Known Stripe test payout")
        print("-" * 46)
        print(f"Payout ID:   {target}")
        print(f"Bank amount: {row['bank_amount']}")
        print(f"Draft total: {row['draft_total']}")
        print(f"Difference:  {row['difference']}")
        print(f"Balanced:    {row['balanced']}")

    print()
    print("V1-V3 files were not replaced.")
    print("No QuickBooks transactions were created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
