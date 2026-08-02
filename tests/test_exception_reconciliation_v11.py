from __future__ import annotations

import pandas as pd

from src.review.exception_reconciliation import (
    build_exception_evidence_reconciliation,
)


def exception_summary():
    return pd.DataFrame([
        {
            "exception_id": "exc_airbnb",
            "processor": "Airbnb",
            "processor_account": "Airbnb",
            "payout_id": "airbnb_payout",
            "bank_amount": 50.00,
            "posting_total": 100.00,
            "difference": 50.00,
            "difference_direction": (
                "Posting total too high"
            ),
        },
        {
            "exception_id": "exc_stripe_low",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "payout_id": "stripe_low",
            "bank_amount": 200.00,
            "posting_total": 100.00,
            "difference": -100.00,
            "difference_direction": (
                "Posting total too low"
            ),
        },
        {
            "exception_id": "exc_stripe_high",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "payout_id": "stripe_high",
            "bank_amount": 100.00,
            "posting_total": 150.00,
            "difference": 50.00,
            "difference_direction": (
                "Posting total too high"
            ),
        },
    ])


def payment_ledger():
    return pd.DataFrame([
        {
            "payment_event_id": "airbnb_adj",
            "processor": "Airbnb",
            "processor_account": "Airbnb",
            "payout_id": "airbnb_payout",
            "transaction_type": "adjustment",
            "transaction_date": "2026-06-01",
            "transaction_id": "ABC",
            "channel_reservation_id": "ABC",
            "guest": "Guest",
            "listing": "Room",
            "source_id": "airbnb_payout",
            "net_amount": -50.00,
        },
        {
            "payment_event_id": "stripe_charge_low",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "payout_id": "stripe_low",
            "transaction_type": "charge",
            "transaction_date": "2026-06-01",
            "transaction_id": "txn1",
            "source_id": "ch_low",
            "net_amount": 100.00,
        },
        {
            "payment_event_id": "stripe_charge_high",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "payout_id": "stripe_high",
            "transaction_type": "charge",
            "transaction_date": "2026-06-01",
            "transaction_id": "txn2",
            "source_id": "ch_high",
            "net_amount": 50.00,
        },
    ])


def posting_history():
    return pd.DataFrame([
        {
            "payment_event_id": "posted_other",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "payout_id": "stripe_high",
            "source_id": "other_source",
            "posting_type": "Original",
            "status": "Active",
            "signed_amount": 150.00,
        }
    ])


def test_airbnb_exact_adjustment_is_detected():
    summary, _, airbnb = (
        build_exception_evidence_reconciliation(
            exception_summary=exception_summary(),
            payment_ledger=payment_ledger(),
            posting_history=posting_history(),
            manual_seeds=pd.DataFrame(),
            reversal_preview=pd.DataFrame(),
        )
    )

    row = summary.loc[
        summary["payout_id"].eq(
            "airbnb_payout"
        )
    ].iloc[0]

    assert row["exact_match_found"] == "Yes"
    assert row["evidence_confidence"] == "High"
    assert row["resolution_blocked"] == "No"
    assert airbnb.loc[
        0, "exact_difference_candidate"
    ] == "Yes"


def test_missing_stripe_charge_is_safe_when_posting_low():
    summary, stripe, _ = (
        build_exception_evidence_reconciliation(
            exception_summary=exception_summary(),
            payment_ledger=payment_ledger(),
            posting_history=posting_history(),
            manual_seeds=pd.DataFrame(),
            reversal_preview=pd.DataFrame(),
        )
    )

    row = summary.loc[
        summary["payout_id"].eq(
            "stripe_low"
        )
    ].iloc[0]

    family = stripe.loc[
        stripe["payout_id"].eq(
            "stripe_low"
        )
    ].iloc[0]

    assert family["family_issue"] == (
        "Missing original charge history"
    )
    assert family["resolution_sign_safe"] == "Safe"
    assert row["resolution_blocked"] == "No"


def test_missing_stripe_charge_is_blocked_when_posting_high():
    summary, stripe, _ = (
        build_exception_evidence_reconciliation(
            exception_summary=exception_summary(),
            payment_ledger=payment_ledger(),
            posting_history=posting_history(),
            manual_seeds=pd.DataFrame(),
            reversal_preview=pd.DataFrame(),
        )
    )

    family = stripe.loc[
        stripe["payout_id"].eq(
            "stripe_high"
        )
    ].iloc[0]

    row = summary.loc[
        summary["payout_id"].eq(
            "stripe_high"
        )
    ].iloc[0]

    assert family["resolution_sign_safe"] == (
        "Unsafe"
    )
    assert row["resolution_blocked"] == "Yes"
    assert "Do not create" in row[
        "recommended_resolution"
    ]
