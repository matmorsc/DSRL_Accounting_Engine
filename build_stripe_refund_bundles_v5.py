from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

from src.reconciliation.stripe_refund_bundles import (
    inherit_stripe_source_metadata,
    reassign_refund_bundles_by_residual,
)
from src.reconciliation.payouts import (
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
from src.review.overrides import (
    apply_manual_payment_matches,
    read_manual_payment_matches,
    read_payout_adjustments,
)


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
SETTINGS = ROOT / "config" / "settings.yaml"
DRAFT_RULES = ROOT / "config" / "deposit_draft_rules.yaml"
POSTING_OVERRIDES = ROOT / "config" / "posting_overrides.csv"
PAYMENT_MATCHES = ROOT / "config" / "manual_payment_matches.csv"
PAYOUT_ADJUSTMENTS = ROOT / "config" / "payout_adjustments.csv"


def read_csv(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run `python run.py` first."
        )
    return pd.read_csv(path)


def main() -> int:
    print("DSRL Stripe Refund-Bundle Pipeline V5")
    print("=" * 46)

    try:
        with SETTINGS.open("r", encoding="utf-8") as handle:
            settings = yaml.safe_load(handle)

        with DRAFT_RULES.open("r", encoding="utf-8") as handle:
            draft_rules = yaml.safe_load(handle)

        payment_ledger = read_csv("payment_ledger.csv")
        payout_ledger = read_csv("payout_ledger.csv")

        payment_ledger = inherit_stripe_source_metadata(
            payment_ledger
        )
        payment_ledger = apply_manual_payment_matches(
            payment_ledger,
            read_manual_payment_matches(PAYMENT_MATCHES),
        )

        payment_ledger, bundle_diagnostics = (
            reassign_refund_bundles_by_residual(
                payment_ledger,
                payout_ledger,
                tolerance=float(
                    settings["matching"]["amount_tolerance"]
                ),
                max_days=30,
            )
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
            "payment_ledger_v5.csv": payment_ledger,
            "stripe_refund_bundle_diagnostics.csv": (
                bundle_diagnostics
            ),
            "payout_ledger_v5.csv": payout_ledger,
            "posting_status_v5.csv": posting_status,
            "payment_allocations_v5.csv": allocations,
            "payment_allocation_diagnostics_v5.csv": (
                allocation_diagnostics
            ),
            "deposit_drafts_v5.csv": drafts,
            "deposit_draft_lines_v5.csv": draft_lines,
        }

        for filename, frame in outputs.items():
            frame.to_csv(PROCESSED / filename, index=False)

    except Exception as exc:
        print(f"ERROR: Stripe Refund-Bundle V5 failed: {exc}")
        return 1

    print(
        f"Refund bundles reviewed:       "
        f"{len(bundle_diagnostics):>6}"
    )
    if not bundle_diagnostics.empty:
        reassigned = (
            bundle_diagnostics["status"]
            .astype(str)
            .eq("Reassigned")
            .sum()
        )
        review = (
            bundle_diagnostics["status"]
            .astype(str)
            .eq("Review Required")
            .sum()
        )
        print(f"Bundles reassigned:            {reassigned:>6}")
        print(f"Bundles still needing review:  {review:>6}")

    print(f"Deposit drafts V5:             {len(drafts):>6}")
    print(f"Deposit draft lines V5:        {len(draft_lines):>6}")
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

    for target in [
        "po_1TqjcpJtejknM735RBYtfOau",
        "po_1TqMRVJtejknM735LuF9w3hi",
    ]:
        target_row = drafts.loc[
            drafts["payout_id"].astype(str).eq(target)
        ]

        print()
        print(f"Known payout: {target}")
        print("-" * 46)

        if target_row.empty:
            print("Not present in eligible draft output.")
            continue

        row = target_row.iloc[0]
        print(f"Bank amount: {row['bank_amount']}")
        print(f"Draft total: {row['draft_total']}")
        print(f"Difference:  {row['difference']}")
        print(f"Balanced:    {row['balanced']}")

    print()
    print("V1-V4 files were not replaced.")
    print("No QuickBooks transactions were created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
