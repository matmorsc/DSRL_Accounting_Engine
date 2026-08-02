from __future__ import annotations

import pandas as pd

from src.review.stripe_seed_candidates import (
    build_stripe_seed_candidates,
)


def _reconciliation(
    *,
    difference: float,
) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "exception_id": "exc1",
            "processor": "Stripe",
            "payout_id": "po1",
            "difference": difference,
            "evidence_confidence": "High",
            "resolution_blocked": "No",
            "exact_match_found": "Yes",
            "recommended_resolution": (
                "Create evidence-backed original charge seed"
            ),
        }
    ])


def _families() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "exception_id": "exc1",
            "payout_id": "po1",
            "processor_account": "Main Guesty",
            "source_id": "ch1",
            "family_issue": (
                "Missing original charge history"
            ),
            "resolution_sign_safe": "Safe",
        }
    ])


def test_safe_exact_candidate_is_generated():
    payments = pd.DataFrame([
        {
            "payout_id": "po1",
            "source_id": "ch1",
            "transaction_type": "charge",
            "payment_event_id": "evt1",
            "transaction_id": "txn1",
            "reservation_id": "r1",
            "channel_reservation_id": "G1",
            "guest": "Guest",
            "listing": "DSRL RV 8",
            "transaction_date": "2026-07-01",
            "gross_amount": 109.09,
            "processor_fee": 3.90,
            "net_amount": 105.19,
        }
    ])

    reservations = pd.DataFrame([
        {
            "reservation_id": "r1",
            "channel_reservation_id": "G1",
            "source": "website",
            "accommodation_revenue": 103.50,
            "state_tax": 3.00,
            "county_tax": 2.59,
            "local_tax": 0.00,
            "total_paid": 109.09,
            "total_refunded": 0.0,
            "total_payout": 105.19,
        }
    ])

    candidates, approvals, diagnostics = (
        build_stripe_seed_candidates(
            reconciliation_summary=_reconciliation(
                difference=-105.19
            ),
            stripe_families=_families(),
            payment_ledger=payments,
            reservations=reservations,
        )
    )

    assert len(candidates) == 4
    assert round(
        candidates["signed_amount"].sum(),
        2,
    ) == 105.19
    assert approvals.iloc[0][
        "approval_eligible"
    ] == "Yes"
    assert diagnostics.iloc[0][
        "diagnostic_type"
    ] == "Candidate Ready"


def test_candidate_is_not_eligible_without_reservation():
    payments = pd.DataFrame([
        {
            "payout_id": "po1",
            "source_id": "ch1",
            "transaction_type": "charge",
            "payment_event_id": "evt1",
            "transaction_id": "txn1",
            "reservation_id": "missing",
            "channel_reservation_id": "",
            "guest": "Guest",
            "listing": "DSRL RV 8",
            "transaction_date": "2026-07-01",
            "gross_amount": 103.90,
            "processor_fee": 3.90,
            "net_amount": 100.00,
        }
    ])

    candidates, approvals, diagnostics = (
        build_stripe_seed_candidates(
            reconciliation_summary=_reconciliation(
                difference=-100.00
            ),
            stripe_families=_families(),
            payment_ledger=payments,
            reservations=pd.DataFrame(),
        )
    )

    assert candidates.empty
    assert approvals.iloc[0][
        "approval_eligible"
    ] == "No"
    assert diagnostics.iloc[0][
        "diagnostic_type"
    ] == "Missing Reservation"


def test_blocked_exception_is_excluded():
    reconciliation = _reconciliation(
        difference=50.00
    )
    reconciliation.loc[
        0, "resolution_blocked"
    ] = "Yes"
    reconciliation.loc[
        0, "recommended_resolution"
    ] = "Do not create missing-original seeds"

    candidates, approvals, diagnostics = (
        build_stripe_seed_candidates(
            reconciliation_summary=reconciliation,
            stripe_families=pd.DataFrame(),
            payment_ledger=pd.DataFrame(),
            reservations=pd.DataFrame(),
        )
    )

    assert candidates.empty
    assert approvals.empty
    assert diagnostics.empty
