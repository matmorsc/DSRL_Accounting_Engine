from __future__ import annotations

import pandas as pd

from src.review.composite_charge_allocation import (
    apply_composite_promotion,
    preview_composite_promotion,
)


def payment_ledger() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "payment_event_id": "evt_wedding",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_wedding",
            "transaction_type": "charge",
            "transaction_date": "2026-07-03",
            "source_id": "ch_wedding",
            "payout_id": "po_wedding",
            "gross_amount": 1565.19,
            "processor_fee": 45.69,
            "net_amount": 1519.50,
        }
    ])


def allocations() -> pd.DataFrame:
    amounts = [
        ("room5", 450.00),
        ("room7", 360.00),
        ("aframe", 675.00),
        ("state", 37.13),
        ("county", 43.06),
        ("fee", -45.69),
    ]
    return pd.DataFrame([
        {
            "composite_group_id": "grp_wedding",
            "allocation_line_id": key,
            "signed_amount": amount,
            "reservation_id": "",
            "channel_reservation_id": "",
            "guest": "",
            "listing": "",
            "account": "Test",
            "class": "Hospitality",
            "description": key,
        }
        for key, amount in amounts
    ])


def approvals(status: str = "Approved") -> pd.DataFrame:
    return pd.DataFrame([
        {
            "composite_group_id": "grp_wedding",
            "group_name": "Wedding Party",
            "payment_event_id": "evt_wedding",
            "source_id": "ch_wedding",
            "payout_id": "po_wedding",
            "gross_amount": 1565.19,
            "processor_fee": 45.69,
            "net_amount": 1519.50,
            "allocation_line_count": 6,
            "approval_eligible": "Yes",
            "approval_status": status,
            "review_notes": "",
        }
    ])


def test_pending_group_is_not_promoted():
    preview, proposed = preview_composite_promotion(
        approvals=approvals("Pending"),
        allocations=allocations(),
        payment_ledger=payment_ledger(),
        existing_history=pd.DataFrame(),
    )

    assert preview.empty
    assert proposed.empty


def test_composite_group_promotes_six_lines():
    preview, history, updated = apply_composite_promotion(
        approvals=approvals(),
        allocations=allocations(),
        payment_ledger=payment_ledger(),
        existing_history=pd.DataFrame(),
    )

    assert preview.iloc[0]["validation_status"] == "Ready to Promote"
    assert len(history) == 6
    assert round(history["signed_amount"].sum(), 2) == 1519.50
    assert updated.iloc[0]["approval_status"] == "Promoted"


def test_composite_promotion_is_idempotent():
    _, first_history, _ = apply_composite_promotion(
        approvals=approvals(),
        allocations=allocations(),
        payment_ledger=payment_ledger(),
        existing_history=pd.DataFrame(),
    )

    second_preview, second_history, _ = apply_composite_promotion(
        approvals=approvals(),
        allocations=allocations(),
        payment_ledger=payment_ledger(),
        existing_history=first_history,
    )

    assert len(second_history) == 6
    assert second_preview.iloc[0]["validation_status"] == "Already Promoted"


def test_bad_total_is_blocked():
    bad_allocations = allocations()
    bad_allocations.loc[
        bad_allocations["allocation_line_id"] == "room5",
        "signed_amount",
    ] = 449.00

    preview, proposed = preview_composite_promotion(
        approvals=approvals(),
        allocations=bad_allocations,
        payment_ledger=payment_ledger(),
        existing_history=pd.DataFrame(),
    )

    assert preview.iloc[0]["validation_status"] == "Blocked"
    assert proposed.empty
