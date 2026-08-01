from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

from src.importers.cognito import (
    find_latest_monthly_renewal,
    normalize_monthly_renewals,
)
from src.importers.discovery import discover_sources
from src.importers.normalize import (
    normalize_airbnb,
    normalize_bank,
    normalize_guesty,
    normalize_quickbooks_inventory,
    normalize_stripe,
)
from src.importers.quickbooks import normalize_quickbooks_gl
from src.matching.engine import build_matches
from src.matching.legacy import match_legacy_payments_to_renewals
from src.posting.batches import build_quickbooks_posting_batches
from src.posting.engine import build_posting_status
from src.reconciliation.airbnb_sequence import (
    assign_airbnb_payouts_by_sequence,
    summarize_airbnb_sequence_groups,
)
from src.reconciliation.engine import build_reconciliation
from src.reconciliation.payouts import (
    build_payment_ledger,
    build_payout_ledger,
    build_payout_reconciliation,
)
from src.reports.inventory import write_source_inventory


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "settings.yaml"
OVERRIDES_PATH = ROOT / "config" / "manual_overrides.csv"
POSTING_OVERRIDES_PATH = ROOT / "config" / "posting_overrides.csv"
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "output"


def save_csv(frame: pd.DataFrame, filename: str) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / filename
    frame.to_csv(path, index=False)
    return path


def main() -> int:
    print("DSRL Accounting Engine")
    print("=" * 40)

    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        settings = yaml.safe_load(handle)

    print(f"Business: {settings['business']['name']}")
    print()

    try:
        sources = discover_sources(ROOT)
        inventory_path = write_source_inventory(
            sources=sources,
            output_dir=OUTPUT_DIR,
        )

        reservations = normalize_guesty(
            sources["Guesty"][0],
            monthly_threshold=int(
                settings["classification"]["monthly_night_threshold"]
            ),
            income_accounts=settings["income_accounts"],
        )

        stripe_frames = []
        for account_name, source_key in [
            ("Main Guesty", "Stripe Main"),
            ("Legacy Cognito", "Stripe Cognito"),
            ("Legacy Keycheck", "Stripe Keycheck"),
        ]:
            stripe_frames.append(
                normalize_stripe(
                    sources[source_key][0],
                    account_name=account_name,
                )
            )

        airbnb_transactions = normalize_airbnb(
            sources["Airbnb"][0]
        )
        (
            airbnb_transactions,
            airbnb_sequence_diagnostics,
        ) = assign_airbnb_payouts_by_sequence(
            airbnb_transactions
        )
        airbnb_sequence_summary = (
            summarize_airbnb_sequence_groups(
                airbnb_transactions
            )
        )

        processor_transactions = pd.concat(
            [
                *stripe_frames,
                airbnb_transactions,
            ],
            ignore_index=True,
        )

        bank_transactions = normalize_bank(sources["Bank"][0])

        quickbooks_inventory = normalize_quickbooks_inventory(
            sources["QuickBooks"]
        )
        quickbooks_gl = normalize_quickbooks_gl(
            sources["QuickBooks"]
        )
        quickbooks_batches = build_quickbooks_posting_batches(
            quickbooks_gl
        )

        renewal_path = find_latest_monthly_renewal(ROOT)
        if renewal_path is not None:
            cognito_renewals = normalize_monthly_renewals(
                renewal_path
            )
        else:
            cognito_renewals = pd.DataFrame()

        matches = build_matches(
            reservations=reservations,
            processor_transactions=processor_transactions,
            amount_tolerance=float(
                settings["matching"]["amount_tolerance"]
            ),
        )

        payment_ledger = build_payment_ledger(
            processor_transactions
        )
        payout_ledger = build_payout_ledger(
            processor_transactions
        )
        payment_ledger, payout_ledger = (
            build_payout_reconciliation(
                payments=payment_ledger,
                payouts=payout_ledger,
                bank_transactions=bank_transactions,
                date_tolerance_days=int(
                    settings["matching"]["bank_date_tolerance_days"]
                ),
                amount_tolerance=float(
                    settings["matching"]["amount_tolerance"]
                ),
            )
        )

        if not cognito_renewals.empty:
            legacy_payment_matches = (
                match_legacy_payments_to_renewals(
                    payment_ledger=payment_ledger,
                    renewals=cognito_renewals,
                    amount_tolerance=float(
                        settings["matching"]["amount_tolerance"]
                    ),
                    date_tolerance_days=10,
                )
            )
        else:
            legacy_payment_matches = pd.DataFrame()

        reconciliation = build_reconciliation(
            reservations=reservations,
            matches=matches,
            processor_transactions=processor_transactions,
            payment_ledger=payment_ledger,
            payout_ledger=payout_ledger,
            overrides_path=OVERRIDES_PATH,
            acquisition_date=settings["business"]["acquisition_date"],
            amount_tolerance=float(
                settings["matching"]["amount_tolerance"]
            ),
        )

        posting_status = build_posting_status(
            payout_ledger=payout_ledger,
            quickbooks_gl=quickbooks_gl,
            quickbooks_batches=quickbooks_batches,
            posting_overrides_path=POSTING_OVERRIDES_PATH,
            assume_posted_through=settings["quickbooks"][
                "assume_posted_through"
            ],
            date_tolerance_days=int(
                settings["quickbooks"][
                    "posting_date_tolerance_days"
                ]
            ),
            amount_tolerance=float(
                settings["quickbooks"]["amount_tolerance"]
            ),
        )

    except Exception as exc:
        print(f"ERROR: Processing failed: {exc}")
        return 1

    outputs = {
        "Reservations": save_csv(
            reservations,
            "reservations.csv",
        ),
        "Processor transactions": save_csv(
            processor_transactions,
            "processor_transactions.csv",
        ),
        "Airbnb sequence diagnostics": save_csv(
            airbnb_sequence_diagnostics,
            "airbnb_sequence_diagnostics.csv",
        ),
        "Airbnb sequence summary": save_csv(
            airbnb_sequence_summary,
            "airbnb_sequence_summary.csv",
        ),
        "Payment ledger": save_csv(
            payment_ledger,
            "payment_ledger.csv",
        ),
        "Payout ledger": save_csv(
            payout_ledger,
            "payout_ledger.csv",
        ),
        "Bank transactions": save_csv(
            bank_transactions,
            "bank_transactions.csv",
        ),
        "QuickBooks inventory": save_csv(
            quickbooks_inventory,
            "quickbooks_inventory.csv",
        ),
        "QuickBooks GL": save_csv(
            quickbooks_gl,
            "quickbooks_gl.csv",
        ),
        "QuickBooks posting batches": save_csv(
            quickbooks_batches,
            "quickbooks_posting_batches.csv",
        ),
        "Reservation matches": save_csv(
            matches,
            "matches.csv",
        ),
        "Reconciliation": save_csv(
            reconciliation,
            "reconciliation.csv",
        ),
        "Posting status": save_csv(
            posting_status,
            "posting_status.csv",
        ),
    }

    if not cognito_renewals.empty:
        outputs["Cognito renewals"] = save_csv(
            cognito_renewals,
            "cognito_renewals.csv",
        )
        outputs["Legacy payment matches"] = save_csv(
            legacy_payment_matches,
            "legacy_payment_matches.csv",
        )

    print("Generated outputs")
    print("-" * 40)

    for label, path in outputs.items():
        rows = len(pd.read_csv(path))
        print(f"{label:<30} {rows:>6} rows  {path.name}")

    print()
    print("Airbnb sequence summary")
    print("-" * 40)
    print(
        f"Balanced groups:   "
        f"{int(airbnb_sequence_summary['balanced'].sum()):>6}"
    )
    print(
        f"Unbalanced groups: "
        f"{int((~airbnb_sequence_summary['balanced']).sum()):>6}"
    )

    print()
    print("QuickBooks posting summary")
    print("-" * 40)

    for status, count in (
        posting_status["posting_status"]
        .value_counts(dropna=False)
        .sort_index()
        .items()
    ):
        print(f"{status:<38} {count:>6}")

    if not cognito_renewals.empty:
        print()
        print("Legacy Cognito matching summary")
        print("-" * 40)

        for status, count in (
            legacy_payment_matches["match_status"]
            .value_counts(dropna=False)
            .sort_index()
            .items()
        ):
            print(f"{status:<38} {count:>6}")

    print()
    print(f"Source inventory:\n{inventory_path}")
    print()
    print(
        "QuickBooks batch, Cognito, and Airbnb sequence "
        "reconciliation passed."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
