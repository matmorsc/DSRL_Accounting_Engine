from __future__ import annotations

import pandas as pd

from src.reconciliation.payouts import (
    assign_payment_events_to_payouts,
    build_payout_reconciliation,
    match_payouts_to_bank,
)


def payments():
    return pd.DataFrame([{
        "payment_event_id": "Main::txn1",
        "processor": "Stripe",
        "processor_account": "Main Guesty",
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
    }])


def payouts():
    return pd.DataFrame([{
        "payout_id": "po1",
        "processor": "Stripe",
        "processor_account": "Main Guesty",
        "transaction_id": "txn_po1",
        "transaction_date": pd.Timestamp("2026-01-04"),
        "payout_amount": 97.0,
        "assigned_event_count": 0,
        "assigned_event_net": 0.0,
        "allocation_difference": 0.0,
        "allocation_status": "Unallocated",
        "bank_transaction_id": "",
        "bank_transaction_date": pd.NaT,
        "bank_amount": 0.0,
        "bank_difference": 0.0,
        "bank_match_status": "Unmatched",
        "bank_match_method": "",
        "source_file": "stripe.csv",
    }])


def bank():
    return pd.DataFrame([{
        "account_id": "bank1",
        "transaction_id": "bank_txn1",
        "transaction_date": pd.Timestamp("2026-01-04"),
        "description": "ACH Deposit STRIPE",
        "amount": 97.0,
        "balance": 1000.0,
        "identified_processor": "Stripe",
        "source_file": "bank.csv",
    }])


def test_assigns_payment():
    result = assign_payment_events_to_payouts(payments(), payouts())
    assert result.loc[0, "payout_id"] == "po1"
    assert result.loc[0, "payout_assignment_status"] == "Assigned"


def test_matches_bank():
    result = match_payouts_to_bank(payouts(), bank())
    assert result.loc[0, "bank_transaction_id"] == "bank_txn1"
    assert result.loc[0, "bank_match_status"] == "Matched"


def test_full_reconciliation():
    payment_result, payout_result = build_payout_reconciliation(
        payments(), payouts(), bank()
    )
    assert payment_result.loc[0, "payout_id"] == "po1"
    assert payout_result.loc[0, "assigned_event_count"] == 1
    assert payout_result.loc[0, "allocation_status"] == "Fully Allocated"
    assert payout_result.loc[0, "bank_match_status"] == "Matched"


def test_pending_future_payout():
    frame = payments()
    frame.loc[0, "available_date"] = pd.Timestamp("2026-01-10")
    result = assign_payment_events_to_payouts(frame, payouts())
    assert (
        result.loc[0, "payout_assignment_status"]
        == "Pending Future Payout"
    )
