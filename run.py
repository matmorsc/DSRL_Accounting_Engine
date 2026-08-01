from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

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
from src.posting.engine import build_posting_status
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

        processor_transactions = pd.concat(
            [
                *stripe_frames,
                normalize_airbnb(sources["Airbnb"][0]),
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
        "Reservations": save_csv(reservations, "reservations.csv"),
        "Processor transactions": save_csv(
            processor_transactions, "processor_transactions.csv"
        ),
        "Payment ledger": save_csv(
            payment_ledger, "payment_ledger.csv"
        ),
        "Payout ledger": save_csv(
            payout_ledger, "payout_ledger.csv"
        ),
        "Bank transactions": save_csv(
            bank_transactions, "bank_transactions.csv"
        ),
        "QuickBooks inventory": save_csv(
            quickbooks_inventory, "quickbooks_inventory.csv"
        ),
        "QuickBooks GL": save_csv(
            quickbooks_gl, "quickbooks_gl.csv"
        ),
        "Reservation matches": save_csv(matches, "matches.csv"),
        "Reconciliation": save_csv(
            reconciliation, "reconciliation.csv"
        ),
        "Posting status": save_csv(
            posting_status, "posting_status.csv"
        ),
    }

    print("Generated outputs")
    print("-" * 40)
    for label, path in outputs.items():
        rows = len(pd.read_csv(path))
        print(f"{label:<26} {rows:>6} rows  {path.name}")

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

    print()
    print("Eligible for draft journal entries")
    print("-" * 40)
    print(
        posting_status["generate_entry"]
        .value_counts(dropna=False)
        .sort_index()
        .to_string()
    )

    print()
    print(f"Source inventory:\n{inventory_path}")
    print()
    print("Posting-control reconciliation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
