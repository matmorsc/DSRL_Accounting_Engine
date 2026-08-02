from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.review.exception_model import (
    build_exception_review_model,
)


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
CONFIG = ROOT / "config"


def read_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing required file: {path}"
        )
    return pd.read_csv(path)


def read_optional(paths: list[Path]) -> pd.DataFrame:
    for path in paths:
        if path.exists():
            return pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
            )
    return pd.DataFrame()


def choose_required(
    names: list[str],
    label: str,
) -> Path:
    for name in names:
        path = PROCESSED / name
        if path.exists():
            return path
    raise FileNotFoundError(
        f"No {label} file found."
    )


def main() -> int:
    print("DSRL Exception Review Model - Phase 11A")
    print("=" * 52)

    try:
        payment_ledger_path = choose_required(
            [
                "payment_ledger_v6.csv",
                "payment_ledger.csv",
            ],
            "payment ledger",
        )

        summary, events, airbnb, stripe = (
            build_exception_review_model(
                posting_package_summary=read_required(
                    PROCESSED
                    / "posting_package_summary_v10.csv"
                ),
                payment_ledger=read_required(
                    payment_ledger_path
                ),
                posting_history=read_required(
                    CONFIG / "posting_history.csv"
                ),
                manual_seeds=read_optional(
                    [
                        CONFIG
                        / "posting_history_manual_seeds.csv"
                    ]
                ),
                reversal_review=read_optional(
                    [
                        PROCESSED
                        / "posting_history_reversal_review.csv"
                    ]
                ),
                reversal_preview=read_optional(
                    [
                        PROCESSED
                        / "posting_history_reversal_preview.csv"
                    ]
                ),
            )
        )

        outputs = {
            "exception_review_summary_v11.csv": summary,
            "exception_event_evidence_v11.csv": events,
            "airbnb_exception_detail_v11.csv": airbnb,
            "stripe_exception_detail_v11.csv": stripe,
        }

        for name, frame in outputs.items():
            frame.to_csv(
                PROCESSED / name,
                index=False,
            )

    except Exception as exc:
        print(
            f"ERROR: Exception Review Model failed: {exc}"
        )
        return 1

    print(
        f"Payment ledger source:      "
        f"{payment_ledger_path.name}"
    )
    print(
        f"Exception payouts:          "
        f"{len(summary):>6}"
    )
    print(
        f"Evidence events:            "
        f"{len(events):>6}"
    )
    print(
        f"Airbnb detail rows:         "
        f"{len(airbnb):>6}"
    )
    print(
        f"Stripe charge families:     "
        f"{len(stripe):>6}"
    )
    print()

    print("Processor")
    print("-" * 52)
    if summary.empty:
        print("No exceptions.")
    else:
        print(
            summary["processor"]
            .value_counts()
            .sort_index()
            .to_string()
        )
    print()

    print("Exception category")
    print("-" * 52)
    if summary.empty:
        print("No exceptions.")
    else:
        print(
            summary["exception_category"]
            .value_counts()
            .sort_index()
            .to_string()
        )
    print()

    print("Recommended review order")
    print("-" * 52)
    if summary.empty:
        print("No exceptions.")
    else:
        print(
            summary[
                [
                    "processor",
                    "bank_transaction_date",
                    "payout_id",
                    "difference",
                    "exception_category",
                    "evidence_confidence",
                ]
            ].to_string(index=False)
        )
    print()
    print("No exception resolutions were applied.")
    print("No posting history was modified.")
    print("No QuickBooks transactions were created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
