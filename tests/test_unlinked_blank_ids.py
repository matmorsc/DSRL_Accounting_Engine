from __future__ import annotations

import pandas as pd

from src.matching.unlinked_review import (
    build_unlinked_stripe_review,
)


def test_blank_ids_are_not_treated_as_links():
    payments = pd.DataFrame([{
        "payment_event_id": "Stripe::txn1",
        "processor": "Stripe",
        "processor_account": "Legacy",
        "transaction_id": "txn1",
        "transaction_type": "charge",
        "transaction_date": pd.Timestamp("2026-01-02"),
        "gross_amount": 650.0,
        "net_amount": 630.0,
        "reservation_id": "",
        "channel_reservation_id": "",
        "guest": "Jessica Adams",
        "listing": "RV Site 3",
        "payout_id": "po1",
        "payout_assignment_status": "Assigned",
    }])

    reservations = pd.DataFrame([{
        "reservation_id": "r1",
        "channel_reservation_id": "",
        "guest": "Jessica Adams",
        "listing": "RV Site 3",
        "confirmation_date": pd.Timestamp("2026-01-01"),
        "check_in": pd.Timestamp("2026-01-05"),
        "total_paid": 650.0,
        "total_payout": 630.0,
        "accommodation_revenue": 650.0,
        "state_tax": 0.0,
        "county_tax": 0.0,
        "local_tax": 0.0,
    }])

    result = build_unlinked_stripe_review(
        payment_ledger=payments,
        reservations=reservations,
        top_n=5,
    )

    assert len(result) == 1
    assert result.loc[0, "candidate_1_reservation_id"] == "r1"
    assert int(result.loc[0, "candidate_1_score"]) >= 90


def test_valid_reservation_id_is_linked():
    payments = pd.DataFrame([{
        "payment_event_id": "Stripe::txn1",
        "processor": "Stripe",
        "processor_account": "Main",
        "transaction_id": "txn1",
        "transaction_type": "charge",
        "transaction_date": pd.Timestamp("2026-01-02"),
        "gross_amount": 100.0,
        "net_amount": 97.0,
        "reservation_id": "r1",
        "channel_reservation_id": "",
        "guest": "Guest",
        "listing": "Room",
        "payout_id": "po1",
        "payout_assignment_status": "Assigned",
    }])

    reservations = pd.DataFrame([{
        "reservation_id": "r1",
        "channel_reservation_id": "",
        "guest": "Guest",
        "listing": "Room",
        "confirmation_date": pd.Timestamp("2026-01-01"),
        "check_in": pd.Timestamp("2026-01-05"),
        "total_paid": 100.0,
        "total_payout": 97.0,
        "accommodation_revenue": 100.0,
        "state_tax": 0.0,
        "county_tax": 0.0,
        "local_tax": 0.0,
    }])

    result = build_unlinked_stripe_review(
        payment_ledger=payments,
        reservations=reservations,
        top_n=5,
    )

    assert result.empty
    assert "candidate_1_reservation_id" in result.columns
