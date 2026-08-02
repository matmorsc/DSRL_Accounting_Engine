from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.review.exception_reconciliation import (
    build_exception_evidence_reconciliation,
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


def read_optional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
    )


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
    print(
        "DSRL Exception Evidence Reconciliation - Phase 11A.1"
    )
    print("=" * 62)

    try:
        payment_ledger_path = choose_required(
            [
                "payment_ledger_v6.csv",
                "payment_ledger.csv",
            ],
            "payment ledger",
        )

        summary, stripe, airbnb = (
            build_exception_evidence_reconciliation(
                exception_summary=read_required(
                    PROCESSED
                    / "exception_review_summary_v11.csv"
                ),
                payment_ledger=read_required(
                    payment_ledger_path
                ),
                posting_history=read_required(
                    CONFIG / "posting_history.csv"
                ),
                manual_seeds=read_optional(
                    CONFIG
                    / "posting_history_manual_seeds.csv"
                ),
                reversal_preview=read_optional(
                    PROCESSED
                    / "posting_history_reversal_preview.csv"
                ),
            )
        )

        outputs = {
            "exception_reconciliation_summary_v11.csv": (
                summary
            ),
            "stripe_family_reconciliation_v11.csv": (
                stripe
            ),
            "airbnb_component_reconciliation_v11.csv": (
                airbnb
            ),
        }

        for name, frame in outputs.items():
            frame.to_csv(
                PROCESSED / name,
                index=False,
            )

    except Exception as exc:
        print(
            f"ERROR: Exception evidence reconciliation failed: "
            f"{exc}"
        )
        return 1

    print(
        f"Payment ledger source:       "
        f"{payment_ledger_path.name}"
    )
    print(
        f"Exception reconciliations:   "
        f"{len(summary):>6}"
    )
    print(
        f"Stripe family rows:          "
        f"{len(stripe):>6}"
    )
    print(
        f"Airbnb component rows:       "
        f"{len(airbnb):>6}"
    )
    print()

    print("Evidence confidence")
    print("-" * 62)
    print(
        summary["evidence_confidence"]
        .value_counts()
        .sort_index()
        .to_string()
    )
    print()

    print("Resolution blocked")
    print("-" * 62)
    print(
        summary["resolution_blocked"]
        .value_counts()
        .sort_index()
        .to_string()
    )
    print()

    print("Reconciliation results")
    print("-" * 62)
    print(
        summary[
            [
                "processor",
                "payout_id",
                "difference",
                "reconciled_gap",
                "exact_match_found",
                "sign_consistency",
                "resolution_blocked",
                "recommended_resolution",
            ]
        ].to_string(index=False)
    )
    print()
    print(
        "No exception resolutions were applied."
    )
    print(
        "No posting history was modified."
    )
    print(
        "No QuickBooks transactions were created."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
