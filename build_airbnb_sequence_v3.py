from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

from src.reconciliation.airbnb_sequence import (
    assign_airbnb_payouts_by_sequence,
    summarize_airbnb_sequence_groups,
)
from src.reconciliation.payouts import (
    build_payment_ledger,
    build_payout_ledger,
    build_payout_reconciliation,
)
from src.posting.engine import build_posting_status
from src.posting.payment_allocations import (
    build_payment_allocations,
)
from src.posting.deposit_drafts_v2 import (
    build_deposit_drafts_v2,
)


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
SETTINGS = ROOT / "config" / "settings.yaml"
DRAFT_RULES = ROOT / "config" / "deposit_draft_rules.yaml"
POSTING_OVERRIDES = ROOT / "config" / "posting_overrides.csv"


def read_csv(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run `python run.py` first."
        )
    return pd.read_csv(path)


def main() -> int:
    print("DSRL Airbnb Sequence Pipeline V3")
    print("=" * 44)

    try:
        with SETTINGS.open("r", encoding="utf-8") as handle:
            settings = yaml.safe_load(handle)

        with DRAFT_RULES.open("r", encoding="utf-8") as handle:
            draft_rules = yaml.safe_load(handle)

        processor_transactions = read_csv(
            "processor_transactions.csv"
        )

        sequenced, sequence_diagnostics = (
            assign_airbnb_payouts_by_sequence(
                processor_transactions
            )
        )
        sequence_summary = (
            summarize_airbnb_sequence_groups(sequenced)
        )

        payment_ledger = build_payment_ledger(sequenced)
        payout_ledger = build_payout_ledger(sequenced)

        payment_ledger, payout_ledger = (
            build_payout_reconciliation(
                payments=payment_ledger,
                payouts=payout_ledger,
                bank_transactions=read_csv(
                    "bank_transactions.csv"
                ),
                date_tolerance_days=int(
                    settings["matching"][
                        "bank_date_tolerance_days"
                    ]
                ),
                amount_tolerance=float(
                    settings["matching"][
                        "amount_tolerance"
                    ]
                ),
            )
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
        )

        outputs = {
            "processor_transactions_v3.csv": sequenced,
            "airbnb_sequence_diagnostics.csv": (
                sequence_diagnostics
            ),
            "airbnb_sequence_summary.csv": sequence_summary,
            "payment_ledger_v3.csv": payment_ledger,
            "payout_ledger_v3.csv": payout_ledger,
            "posting_status_v3.csv": posting_status,
            "payment_allocations_v3.csv": allocations,
            "payment_allocation_diagnostics_v3.csv": (
                allocation_diagnostics
            ),
            "deposit_drafts_v3.csv": drafts,
            "deposit_draft_lines_v3.csv": draft_lines,
        }

        for filename, frame in outputs.items():
            frame.to_csv(PROCESSED / filename, index=False)

    except Exception as exc:
        print(f"ERROR: Airbnb Sequence V3 failed: {exc}")
        return 1

    print(
        f"Airbnb payouts grouped:       "
        f"{len(sequence_summary):>6}"
    )
    print(
        f"Airbnb groups balanced:       "
        f"{int(sequence_summary['balanced'].sum()):>6}"
    )
    print(
        f"Airbnb groups unbalanced:     "
        f"{int((~sequence_summary['balanced']).sum()):>6}"
    )
    print()

    print("Deposit Draft V3 status")
    print("-" * 44)
    for status, count in (
        drafts["draft_status"]
        .value_counts(dropna=False)
        .sort_index()
        .items()
    ):
        print(f"{status:<32} {count:>6}")

    print()
    print("Deposit Draft V3 balance")
    print("-" * 44)
    print(
        drafts["balanced"]
        .value_counts(dropna=False)
        .sort_index()
        .to_string()
    )

    print()
    print("V1 and V2 files were not replaced.")
    print("No QuickBooks transactions were created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
