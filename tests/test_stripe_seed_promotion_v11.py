import pandas as pd
import pytest
from src.review.stripe_seed_promotion import apply_stripe_seed_promotion, preview_stripe_seed_promotion


def approvals(status="Approved"):
    return pd.DataFrame([{
        "candidate_group_id": "grp1", "payout_id": "po1", "processor_account": "Main Guesty",
        "source_id": "ch1", "payment_event_id": "evt1", "guest": "Paul", "listing": "Room 4",
        "proposed_seed_effect": 91.56, "remaining_difference_after_seed": 0,
        "line_count": 2, "sign_safe": "Yes", "exact_match": "Yes",
        "approval_eligible": "Yes", "approval_status": status, "review_notes": "",
    }])


def candidates():
    common = {
        "candidate_group_id": "grp1", "payout_id": "po1", "processor_account": "Main Guesty",
        "source_id": "ch1", "payment_event_id": "evt1", "transaction_id": "txn1",
        "reservation_id": "r1", "channel_reservation_id": "G1", "guest": "Paul",
        "listing": "Room 4", "transaction_date": "2026-06-16",
        "class": "Hospitality", "allocation_method": "Canceled Booking.com Gross",
        "evidence_level": "High", "evidence_source": "Stripe + Guesty",
        "evidence_reason": "Gross confirmed",
    }
    return pd.DataFrame([
        {**common, "candidate_id": "c1", "account": "Motel Rent - Short Term", "description": "Room 4", "signed_amount": 95.0},
        {**common, "candidate_id": "c2", "account": "Bank Charges & Fees:Stripe Processing Fees", "description": "Stripe fees", "signed_amount": -3.44},
    ])


def test_pending_is_not_promoted():
    preview, proposed = preview_stripe_seed_promotion(approvals=approvals("Pending"), candidates=candidates(), existing_history=pd.DataFrame())
    assert preview.empty and proposed.empty


def test_approved_group_is_promotable():
    preview, proposed = preview_stripe_seed_promotion(approvals=approvals(), candidates=candidates(), existing_history=pd.DataFrame())
    assert preview.iloc[0]["validation_status"] == "Ready to Promote"
    assert len(proposed) == 2
    assert round(proposed["signed_amount"].sum(), 2) == 91.56


def test_apply_is_idempotent():
    _, history, _ = apply_stripe_seed_promotion(approvals=approvals(), candidates=candidates(), existing_history=pd.DataFrame())
    preview, history2, approvals2 = apply_stripe_seed_promotion(approvals=approvals(), candidates=candidates(), existing_history=history)
    assert len(history2) == 2
    assert preview.iloc[0]["validation_status"] == "Already Promoted"
    assert approvals2.iloc[0]["approval_status"] == "Promoted"


def test_invalid_group_blocks_changes():
    bad = approvals(); bad.loc[0, "remaining_difference_after_seed"] = 5
    with pytest.raises(ValueError):
        apply_stripe_seed_promotion(approvals=bad, candidates=candidates(), existing_history=pd.DataFrame())
