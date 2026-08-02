from __future__ import annotations

import pandas as pd

from src.review.original_charge_reconstruction import (
    apply_reconstruction_promotion,
    build_reconstruction_candidates,
    reconstruct_tax_allocation,
)


def test_exact_tax_reconstruction():
    revenue, state_tax, local_tax = reconstruct_tax_allocation(
        gross_amount=115.91,
        state_rate=0.025,
        local_rate=0.029,
    )

    assert revenue == 109.97
    assert state_tax == 2.75
    assert local_tax == 3.19
    assert round(revenue + state_tax + local_tax, 2) == 115.91


def test_candidate_builds_from_zeroed_reservation():
    payment = pd.DataFrame([
        {
            "payment_event_id": "evt1",
            "processor": "Stripe",
            "transaction_type": "charge",
            "source_id": "ch1",
            "payout_id": "po1",
            "reservation_id": "r1",
            "channel_reservation_id": "GY-1",
            "guest": "Johnathon Zawadzki",
            "listing": "DSRL RV 2",
            "gross_amount": 115.91,
            "processor_fee": 4.12,
            "net_amount": 111.79,
        }
    ])
    reservations = pd.DataFrame([
        {
            "reservation_id": "r1",
            "guest": "Johnathon Zawadzki",
            "listing": "DSRL RV 2",
            "property_class": "RV",
            "accommodation_revenue": 0.0,
            "state_tax": 0.0,
            "county_tax": 0.0,
            "local_tax": 0.0,
            "total_refunded": 0.0,
        }
    ])
    tax_config = pd.DataFrame([
        {
            "effective_date": "2026-01-01",
            "state_rate": 0.025,
            "local_rate": 0.029,
        }
    ])

    candidates = build_reconstruction_candidates(
        payment_ledger=payment,
        reservations=reservations,
        tax_config=tax_config,
    )

    assert len(candidates) == 1
    row = candidates.iloc[0]
    assert row["approval_eligible"] == "Yes"
    assert row["reconstructed_revenue"] == 109.97
    assert row["candidate_total"] == 111.79


def test_approved_candidate_promotes_four_lines():
    approvals = pd.DataFrame([
        {
            "candidate_group_id": "grp1",
            "payment_event_id": "evt1",
            "source_id": "ch1",
            "payout_id": "po1",
            "reservation_id": "r1",
            "channel_reservation_id": "GY-1",
            "guest": "Johnathon Zawadzki",
            "listing": "DSRL RV 2",
            "property_class": "RV",
            "gross_amount": 115.91,
            "processor_fee": 4.12,
            "net_amount": 111.79,
            "state_rate": 0.025,
            "local_rate": 0.029,
            "reconstructed_revenue": 109.97,
            "reconstructed_state_tax": 2.75,
            "reconstructed_local_tax": 3.19,
            "candidate_total": 111.79,
            "approval_eligible": "Yes",
            "approval_status": "Approved",
            "review_notes": "",
        }
    ])

    preview, history, updated = apply_reconstruction_promotion(
        approvals=approvals,
        existing_history=pd.DataFrame(),
    )

    assert preview.iloc[0]["validation_status"] == "Ready to Promote"
    assert len(history) == 4
    assert round(history["signed_amount"].sum(), 2) == 111.79
    assert updated.iloc[0]["approval_status"] == "Promoted"


def test_promotion_is_idempotent():
    approvals = pd.DataFrame([
        {
            "candidate_group_id": "grp1",
            "payment_event_id": "evt1",
            "source_id": "ch1",
            "payout_id": "po1",
            "reservation_id": "r1",
            "channel_reservation_id": "GY-1",
            "guest": "Johnathon Zawadzki",
            "listing": "DSRL RV 2",
            "property_class": "RV",
            "gross_amount": 115.91,
            "processor_fee": 4.12,
            "net_amount": 111.79,
            "state_rate": 0.025,
            "local_rate": 0.029,
            "reconstructed_revenue": 109.97,
            "reconstructed_state_tax": 2.75,
            "reconstructed_local_tax": 3.19,
            "candidate_total": 111.79,
            "approval_eligible": "Yes",
            "approval_status": "Approved",
            "review_notes": "",
        }
    ])

    _, first_history, _ = apply_reconstruction_promotion(
        approvals=approvals,
        existing_history=pd.DataFrame(),
    )
    second_preview, second_history, _ = apply_reconstruction_promotion(
        approvals=approvals,
        existing_history=first_history,
    )

    assert len(second_history) == 4
    assert second_preview.iloc[0]["validation_status"] == "Already Promoted"
