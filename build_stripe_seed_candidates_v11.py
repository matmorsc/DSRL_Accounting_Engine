from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.review.stripe_seed_candidates import (
    build_stripe_seed_candidates,
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
        "DSRL Canceled Reservation Reconstruction - Phase 11C"
    )
    print("=" * 68)

    try:
        payment_ledger_path = choose_required(
            [
                "payment_ledger_v6.csv",
                "payment_ledger.csv",
            ],
            "payment ledger",
        )
        reservations_path = choose_required(
            ["reservations.csv"],
            "reservations",
        )

        candidates, approvals, diagnostics = (
            build_stripe_seed_candidates(
                reconciliation_summary=read_required(
                    PROCESSED
                    / "exception_reconciliation_summary_v11.csv"
                ),
                stripe_families=read_required(
                    PROCESSED
                    / "stripe_family_reconciliation_v11.csv"
                ),
                payment_ledger=read_required(
                    payment_ledger_path
                ),
                reservations=read_required(
                    reservations_path
                ),
            )
        )

        candidates_path = (
            PROCESSED
            / "stripe_seed_candidates_v11.csv"
        )
        approvals_path = (
            CONFIG
            / "stripe_seed_approvals_v11.csv"
        )
        diagnostics_path = (
            PROCESSED
            / "stripe_seed_candidate_diagnostics_v11.csv"
        )

        candidates.to_csv(
            candidates_path,
            index=False,
        )
        approvals.to_csv(
            approvals_path,
            index=False,
        )
        diagnostics.to_csv(
            diagnostics_path,
            index=False,
        )

    except Exception as exc:
        print(
            "ERROR: Canceled reservation reconstruction "
            f"failed: {exc}"
        )
        return 1

    print(
        f"Payment ledger source:       "
        f"{payment_ledger_path.name}"
    )
    print(
        f"Reservations source:         "
        f"{reservations_path.name}"
    )
    print(
        f"Candidate posting lines:     "
        f"{len(candidates):>6}"
    )
    print(
        f"Candidate source groups:     "
        f"{len(approvals):>6}"
    )
    print(
        f"Approval eligible groups:    "
        f"{int((approvals['approval_eligible'] == 'Yes').sum()) if not approvals.empty else 0:>6}"
    )
    print()

    print("Candidate controls")
    print("-" * 68)
    if approvals.empty:
        print("No candidates.")
    else:
        print(
            approvals[
                [
                    "payout_id",
                    "guest",
                    "listing",
                    "reservation_source",
                    "allocation_method",
                    "evidence_level",
                    "proposed_seed_effect",
                    "remaining_difference_after_seed",
                    "approval_eligible",
                    "approval_status",
                ]
            ].to_string(index=False)
        )

    print()
    print("Diagnostics")
    print("-" * 68)
    if diagnostics.empty:
        print("No diagnostics.")
    else:
        print(
            diagnostics[
                [
                    "payout_id",
                    "guest",
                    "reservation_source",
                    "charge_gross",
                    "gross_evidence_match",
                    "allocation_method",
                    "reconstructed_gross",
                    "diagnostic_type",
                ]
            ].to_string(index=False)
        )

    print()
    print(f"Candidate lines: {candidates_path}")
    print(f"Approval file:   {approvals_path}")
    print(f"Diagnostics:     {diagnostics_path}")
    print()
    print("No seed candidates were promoted.")
    print("No posting history was modified.")
    print("No QuickBooks transactions were created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
