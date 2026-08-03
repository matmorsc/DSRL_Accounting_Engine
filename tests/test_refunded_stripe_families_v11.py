from __future__ import annotations

import pandas as pd

from src.review.refunded_stripe_families import (
    apply_refunded_family_promotion,
    build_refunded_family_candidates,
)


def payment_ledger() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "payment_event_id": "charge_evt",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_charge",
            "transaction_type": "charge",
            "transaction_date": "2026-05-25",
            "source_id": "ch_ryan",
            "payout_id": "po_ryan",
            "reservation_id": "r_ryan",
            "channel_reservation_id": "GY-1",
            "guest": "Ryan Staab",
            "listing": "DSRL RV 6",
            "gross_amount": 289.86,
            "processor_fee": 9.87,
            "net_amount": 279.99,
        },
        {
            "payment_event_id": "refund_evt",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_refund",
            "transaction_type": "refund",
            "transaction_date": "2026-05-26",
            "source_id": "ch_ryan",
            "payout_id": "po_ryan",
            "reservation_id": "r_ryan",
            "channel_reservation_id": "GY-1",
            "guest": "Ryan Staab",
            "listing": "DSRL RV 6",
            "gross_amount": -289.86,
            "processor_fee": 0.0,
            "net_amount": -289.86,
        },
        {
            "payment_event_id": "adjust_evt",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_adjust",
            "transaction_type": "adjustment",
            "transaction_date": "2026-05-26",
            "source_id": "ch_ryan",
            "payout_id": "po_ryan",
            "reservation_id": "r_ryan",
            "channel_reservation_id": "GY-1",
            "guest": "Ryan Staab",
            "listing": "DSRL RV 6",
            "gross_amount": 1.16,
            "processor_fee": 0.0,
            "net_amount": 1.16,
        },
    ])


def reservations() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "reservation_id": "r_ryan",
            "accommodation_revenue": 0.0,
            "total_paid": 0.0,
            "total_refunded": 289.86,
            "total_payout": 0.0,
        }
    ])


def test_candidate_detects_refunded_fee_family():
    candidates = build_refunded_family_candidates(
        payment_ledger=payment_ledger(),
        reservations=reservations(),
    )

    assert len(candidates) == 1
    row = candidates.iloc[0]
    assert row["approval_eligible"] == "Yes"
    assert row["family_net"] == -8.71


def test_approved_family_promotes_fee_and_adjustment():
    approvals = build_refunded_family_candidates(
        payment_ledger=payment_ledger(),
        reservations=reservations(),
    )
    approvals.loc[
        0,
        "approval_status",
    ] = "Approved"

    preview, history, updated = (
        apply_refunded_family_promotion(
            approvals=approvals,
            existing_history=pd.DataFrame(),
        )
    )

    assert preview.iloc[0][
        "validation_status"
    ] == "Ready to Promote"
    assert len(history) == 2
    assert round(
        history["signed_amount"].sum(),
        2,
    ) == -8.71
    assert updated.iloc[0][
        "approval_status"
    ] == "Promoted"


def test_promotion_is_idempotent():
    approvals = build_refunded_family_candidates(
        payment_ledger=payment_ledger(),
        reservations=reservations(),
    )
    approvals.loc[
        0,
        "approval_status",
    ] = "Approved"

    _, first_history, _ = (
        apply_refunded_family_promotion(
            approvals=approvals,
            existing_history=pd.DataFrame(),
        )
    )

    second_preview, second_history, _ = (
        apply_refunded_family_promotion(
            approvals=approvals,
            existing_history=first_history,
        )
    )

    assert len(second_history) == 2
    assert second_preview.iloc[0][
        "validation_status"
    ] == "Already Promoted"
