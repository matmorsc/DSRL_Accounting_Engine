from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

from src.importers.stripe_payout_reconciliation import (
    discover_payout_reconciliation_files,
    normalize_payout_reconciliation,
)
from src.reconciliation.stripe_payout_membership import (
    apply_exact_stripe_payout_membership,
)
from src.reconciliation.stripe_refund_bundles import (
    inherit_stripe_source_metadata,
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
ACCOUNT_MAP = (
    ROOT / "config" / "stripe_payout_account_mapping.yaml"
)
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
    print("DSRL Stripe Payout Reconciliation V6")
    print("=" * 46)

    try:
        with SETTINGS.open("r", encoding="utf-8") as handle:
            settings = yaml.safe_load(handle)

        with DRAFT_RULES.open("r", encoding="utf-8") as handle:
            draft_rules = yaml.safe_load(handle)

        with ACCOUNT_MAP.open("r", encoding="utf-8") as handle:
            account_mapping = yaml.safe_load(handle) or {}

        report_files = (
            discover_payout_reconciliation_files(ROOT)
        )
        if not report_files:
            raise FileNotFoundError(
                "No CSV files found in "
                "data/raw/stripe/payout_reconciliation"
            )

        membership = normalize_payout_reconciliation(
            report_files,
            account_mapping=account_mapping,
        )

        unmapped_accounts = sorted(
            {
                name
                for name in membership.loc[
                    membership["processor_account"].eq(""),
                    "stripe_account_name",
                ]
                if str(name).strip()
            }
        )
        if unmapped_accounts:
            raise ValueError(
                "Unmapped Stripe report account names: "
                + ", ".join(unmapped_accounts)
            )

        payment_ledger = read_csv("payment_ledger.csv")

        # Stripe refund/adjustment rows often have no reservation metadata.
        # Inherit it from the original charge sharing the same Stripe Source.
        payment_ledger = inherit_stripe_source_metadata(
            payment_ledger
        )

        payment_ledger = apply_manual_payment_matches(
            payment_ledger,
            read_manual_payment_matches(PAYMENT_MATCHES),
        )

        payment_ledger, membership_diagnostics = (
            apply_exact_stripe_payout_membership(
                payment_ledger,
                membership,
            )
        )

        payout_ledger = summarize_payout_allocations(
            payment_ledger,
            read_csv("payout_ledger.csv"),
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
                settings["quickbooks"]["amount_tolerance"]
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
            "stripe_payout_membership.csv": membership,
            "stripe_payout_membership_diagnostics.csv": (
                membership_diagnostics
            ),
            "payment_ledger_v6.csv": payment_ledger,
            "payout_ledger_v6.csv": payout_ledger,
            "posting_status_v6.csv": posting_status,
            "payment_allocations_v6.csv": allocations,
            "payment_allocation_diagnostics_v6.csv": (
                allocation_diagnostics
            ),
            "deposit_drafts_v6.csv": drafts,
            "deposit_draft_lines_v6.csv": draft_lines,
        }

        for filename, frame in outputs.items():
            frame.to_csv(PROCESSED / filename, index=False)

    except Exception as exc:
        print(
            f"ERROR: Stripe Payout Reconciliation V6 failed: "
            f"{exc}"
        )
        return 1

    matched_events = (
        payment_ledger["exact_payout_membership_applied"]
        .astype(str)
        .eq("Yes")
        .sum()
    )
    inherited_events = (
        payment_ledger["stripe_metadata_inherited"]
        .astype(str)
        .eq("Yes")
        .sum()
        if "stripe_metadata_inherited" in payment_ledger.columns
        else 0
    )
    changed_events = (
        membership_diagnostics["assignment_changed"]
        .astype(str)
        .eq("Yes")
        .sum()
        if not membership_diagnostics.empty
        else 0
    )

    print(f"Report files:                         {len(report_files):>6}")
    print(f"Payout membership rows:             {len(membership):>6}")
    print(f"Payment events matched exactly:     {matched_events:>6}")
    print(f"Stripe metadata inherited:          {inherited_events:>6}")
    print(f"Assignments corrected:              {changed_events:>6}")
    print(f"Deposit drafts V6:                  {len(drafts):>6}")
    print(f"Deposit draft lines V6:             {len(draft_lines):>6}")
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
    print("Primary pipeline and V1-V5 files were not replaced.")
    print("No QuickBooks transactions were created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
