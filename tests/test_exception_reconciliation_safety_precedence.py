from __future__ import annotations

import pandas as pd

from src.review.exception_reconciliation import (
    build_exception_evidence_reconciliation,
)


def test_unsafe_exact_match_is_blocked_before_recommendation():
    exception_summary = pd.DataFrame([
        {
            "exception_id": "exc_high",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "payout_id": "po_high",
            "bank_amount": 100.00,
            "posting_total": 150.00,
            "difference": 50.00,
            "difference_direction": "Posting total too high",
        }
    ])

    payment_ledger = pd.DataFrame([
        {
            "payment_event_id": "charge_high",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "payout_id": "po_high",
            "transaction_type": "charge",
            "transaction_date": "2026-07-01",
            "transaction_id": "txn_high",
            "source_id": "ch_high",
            "net_amount": 50.00,
        }
    ])

    posting_history = pd.DataFrame([
        {
            "payment_event_id": "other",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "payout_id": "po_high",
            "source_id": "other_source",
            "posting_type": "Original",
            "status": "Active",
            "signed_amount": 150.00,
        }
    ])

    summary, stripe, _ = (
        build_exception_evidence_reconciliation(
            exception_summary=exception_summary,
            payment_ledger=payment_ledger,
            posting_history=posting_history,
            manual_seeds=pd.DataFrame(),
            reversal_preview=pd.DataFrame(),
        )
    )

    row = summary.iloc[0]
    family = stripe.iloc[0]

    assert family["resolution_sign_safe"] == "Unsafe"
    assert row["exact_match_found"] == "Yes"
    assert row["resolution_blocked"] == "Yes"
    assert row["sign_consistency"] == "Unsafe"
    assert row["recommended_resolution"].startswith(
        "Do not create"
    )
