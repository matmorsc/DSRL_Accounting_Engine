from __future__ import annotations

import pandas as pd

from src.review.stripe_seed_candidates import (
    build_stripe_seed_candidates,
)


def test_empty_inputs_return_typed_empty_frames():
    candidates, approvals, diagnostics = (
        build_stripe_seed_candidates(
            reconciliation_summary=pd.DataFrame(),
            stripe_families=pd.DataFrame(),
            payment_ledger=pd.DataFrame(),
            reservations=pd.DataFrame(),
        )
    )

    assert candidates.empty
    assert approvals.empty
    assert diagnostics.empty
    assert "candidate_id" in candidates.columns
    assert "candidate_group_id" in approvals.columns
    assert "diagnostic_type" in diagnostics.columns


def test_rejected_candidate_exposes_reservation_mismatch():
    reconciliation = pd.DataFrame([
        {
            "exception_id": "exc1",
            "processor": "Stripe",
            "payout_id": "po1",
            "difference": -91.56,
            "evidence_confidence": "High",
            "resolution_blocked": "No",
            "exact_match_found": "Yes",
            "recommended_resolution": (
                "Create evidence-backed original charge seed"
            ),
        }
    ])

    families = pd.DataFrame([
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
            "listing": "DSRL Lodge Room 4",
            "transaction_date": "2026-07-01",
            "gross_amount": 95.00,
            "processor_fee": 3.44,
            "net_amount": 91.56,
        }
    ])

    reservations = pd.DataFrame([
        {
            "reservation_id": "r1",
            "channel_reservation_id": "G1",
            "accommodation_revenue": 90.00,
            "state_tax": 0.00,
            "county_tax": 0.00,
            "local_tax": 0.00,
        }
    ])

    candidates, approvals, diagnostics = (
        build_stripe_seed_candidates(
            reconciliation_summary=reconciliation,
            stripe_families=families,
            payment_ledger=payments,
            reservations=reservations,
        )
    )

    assert candidates.empty
    assert approvals.iloc[0]["approval_eligible"] == "No"

    diagnostic = diagnostics.iloc[0]
    assert diagnostic["diagnostic_type"] == (
        "Reservation Gross Mismatch"
    )
    assert diagnostic["charge_gross"] == 95.00
    assert diagnostic[
        "reservation_component_total"
    ] == 90.00
    assert diagnostic[
        "gross_component_difference"
    ] == -5.00
    assert "Possible causes" in diagnostic[
        "possible_cause"
    ]


def test_ready_candidate_still_generates_lines():
    reconciliation = pd.DataFrame([
        {
            "exception_id": "exc1",
            "processor": "Stripe",
            "payout_id": "po1",
            "difference": -91.56,
            "evidence_confidence": "High",
            "resolution_blocked": "No",
            "exact_match_found": "Yes",
            "recommended_resolution": (
                "Create evidence-backed original charge seed"
            ),
        }
    ])

    families = pd.DataFrame([
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
            "listing": "DSRL Lodge Room 4",
            "transaction_date": "2026-07-01",
            "gross_amount": 95.00,
            "processor_fee": 3.44,
            "net_amount": 91.56,
        }
    ])

    reservations = pd.DataFrame([
        {
            "reservation_id": "r1",
            "channel_reservation_id": "G1",
            "accommodation_revenue": 95.00,
            "state_tax": 0.00,
            "county_tax": 0.00,
            "local_tax": 0.00,
        }
    ])

    candidates, approvals, diagnostics = (
        build_stripe_seed_candidates(
            reconciliation_summary=reconciliation,
            stripe_families=families,
            payment_ledger=payments,
            reservations=reservations,
        )
    )

    assert len(candidates) == 2
    assert round(
        candidates["signed_amount"].sum(),
        2,
    ) == 91.56
    assert approvals.iloc[0]["approval_eligible"] == "Yes"
    assert diagnostics.iloc[0]["diagnostic_type"] == (
        "Candidate Ready"
    )
