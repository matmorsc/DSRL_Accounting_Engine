from __future__ import annotations

import pandas as pd

from src.reconciliation.payouts import (
    assign_payment_events_to_payouts,
)
from src.matching.unlinked_review import (
    build_unlinked_stripe_review,
)


def test_airbnb_exact_reference_beats_date_rule():
    payments = pd.DataFrame([
        {
            "payment_event_id": "Airbnb::HM1",
            "processor": "Airbnb",
            "processor_account": "Airbnb",
            "transaction_id": "HM1",
            "transaction_type": "reservation",
            "source_id": "G-SECOND",
            "transaction_date": pd.Timestamp("2026-07-01"),
            "available_date": pd.Timestamp("2026-07-02"),
            "gross_amount": 200.0,
            "processor_fee": 6.0,
            "net_amount": 194.0,
            "reservation_id": "",
            "channel_reservation_id": "HM1",
            "guest": "Guest",
            "listing": "Cabin",
            "payout_id": "",
            "payout_assignment_status": "Unassigned",
            "payout_assignment_method": "",
            "payout_date": pd.NaT,
            "source_file": "airbnb.csv",
        }
    ])

    payouts = pd.DataFrame([
        {
            "payout_id": "G-FIRST",
            "processor": "Airbnb",
            "processor_account": "Airbnb",
            "transaction_id": "p1",
            "transaction_date": pd.Timestamp("2026-07-02"),
        },
        {
            "payout_id": "G-SECOND",
            "processor": "Airbnb",
            "processor_account": "Airbnb",
            "transaction_id": "p2",
            "transaction_date": pd.Timestamp("2026-07-02"),
        },
    ])

    result = assign_payment_events_to_payouts(
        payments,
        payouts,
    )

    assert result.loc[0, "payout_id"] == "G-SECOND"
    assert (
        result.loc[0, "payout_assignment_method"]
        == "Exact processor payout reference"
    )


def test_date_fallback_still_works():
    payments = pd.DataFrame([
        {
            "payment_event_id": "Stripe::txn1",
            "processor": "Stripe",
            "processor_account": "Main",
            "transaction_id": "txn1",
            "transaction_type": "charge",
            "source_id": "ch1",
            "transaction_date": pd.Timestamp("2026-01-01"),
            "available_date": pd.Timestamp("2026-01-03"),
            "gross_amount": 100.0,
            "processor_fee": 3.0,
            "net_amount": 97.0,
            "reservation_id": "r1",
            "channel_reservation_id": "",
            "guest": "Guest",
            "listing": "Room",
            "payout_id": "",
            "payout_assignment_status": "Unassigned",
            "payout_assignment_method": "",
            "payout_date": pd.NaT,
            "source_file": "stripe.csv",
        }
    ])

    payouts = pd.DataFrame([
        {
            "payout_id": "po1",
            "processor": "Stripe",
            "processor_account": "Main",
            "transaction_id": "p1",
            "transaction_date": pd.Timestamp("2026-01-04"),
        }
    ])

    result = assign_payment_events_to_payouts(
        payments,
        payouts,
    )

    assert result.loc[0, "payout_id"] == "po1"
    assert (
        result.loc[0, "payout_assignment_method"]
        == "First payout on or after available date"
    )


def test_unlinked_review_scores_exact_candidate():
    payments = pd.DataFrame([
        {
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
        }
    ])

    reservations = pd.DataFrame([
        {
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
        }
    ])

    result = build_unlinked_stripe_review(
        payment_ledger=payments,
        reservations=reservations,
        top_n=5,
    )

    assert result.loc[0, "candidate_1_reservation_id"] == "r1"
    assert int(result.loc[0, "candidate_1_score"]) >= 90
