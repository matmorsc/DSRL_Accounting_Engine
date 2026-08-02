from __future__ import annotations

import pandas as pd

from src.review.exception_model import (
    build_exception_review_model,
)


def test_exception_model_smoke():
    posting_package_summary = pd.DataFrame([
        {
            "payout_id": "AIRBNB-PAYOUT-1",
            "processor": "Airbnb",
            "processor_account": "Airbnb",
            "bank_transaction_date": "2026-06-30",
            "bank_description": "AIRBNB",
            "bank_amount": 14.87,
            "posting_total": 68.41,
            "bank_difference": 53.54,
            "confidence": "Needs Review",
        },
        {
            "payout_id": "po_stripe",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "bank_transaction_date": "2026-07-07",
            "bank_description": "STRIPE",
            "bank_amount": 1670.55,
            "posting_total": 151.05,
            "bank_difference": -1519.50,
            "confidence": "Needs Review",
        },
    ])

    payment_ledger = pd.DataFrame([
        {
            "payment_event_id": "Airbnb::ABC",
            "processor": "Airbnb",
            "processor_account": "Airbnb",
            "transaction_id": "ABC",
            "transaction_type": "adjustment",
            "transaction_date": "2026-06-30",
            "source_id": "AIRBNB-PAYOUT-1",
            "payout_id": "AIRBNB-PAYOUT-1",
            "reservation_id": "",
            "channel_reservation_id": "ABC",
            "guest": "Guest",
            "listing": "Room",
            "gross_amount": -53.54,
            "processor_fee": 0.0,
            "net_amount": -53.54,
        },
        {
            "payment_event_id": "Stripe::charge",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_charge",
            "transaction_type": "charge",
            "transaction_date": "2026-07-01",
            "source_id": "ch_missing",
            "payout_id": "po_stripe",
            "reservation_id": "r1",
            "channel_reservation_id": "G1",
            "guest": "Guest",
            "listing": "RV 8",
            "gross_amount": 105.19,
            "processor_fee": 3.90,
            "net_amount": 101.29,
        },
    ])

    summary, events, airbnb, stripe = (
        build_exception_review_model(
            posting_package_summary=posting_package_summary,
            payment_ledger=payment_ledger,
            posting_history=pd.DataFrame(),
            manual_seeds=pd.DataFrame(),
            reversal_review=pd.DataFrame(),
            reversal_preview=pd.DataFrame(),
        )
    )

    assert len(summary) == 2
    assert len(events) == 2
    assert len(airbnb) == 1
    assert len(stripe) == 1
