from __future__ import annotations
import pandas as pd
from src.posting.history import (
    POSTING_HISTORY_COLUMNS,
    build_proposed_posting_history,
    validate_posting_history,
)

def allocations():
    return pd.DataFrame([
        {
            "payment_event_id":"evt1","payout_id":"po1","processor":"Stripe",
            "processor_account":"Main Guesty","transaction_id":"txn1",
            "transaction_type":"charge","transaction_date":"2026-07-01",
            "reservation_id":"r1","channel_reservation_id":"G1","guest":"Guest",
            "listing":"Room 1","allocation_type":"Revenue",
            "account":"Motel Rent - Short Term","description":"Room 1",
            "amount":100.0,"class":"Hospitality","match_method":"Reservation ID",
        },
        {
            "payment_event_id":"evt1","payout_id":"po1","processor":"Stripe",
            "processor_account":"Main Guesty","transaction_id":"txn1",
            "transaction_type":"charge","transaction_date":"2026-07-01",
            "reservation_id":"r1","channel_reservation_id":"G1","guest":"Guest",
            "listing":"Room 1","allocation_type":"Processor Fee",
            "account":"Bank Charges & Fees:Stripe Processing Fees",
            "description":"Stripe processing fees","amount":-3.0,
            "class":"Hospitality","match_method":"Reservation ID",
        },
    ])

def ledger():
    return pd.DataFrame([{"payment_event_id":"evt1","source_id":"ch_1"}])

def empty_history():
    return pd.DataFrame(columns=POSTING_HISTORY_COLUMNS)

def test_ids_are_deterministic():
    first, _ = build_proposed_posting_history(
        allocations=allocations(), payment_ledger=ledger(),
        existing_history=empty_history(), created_at="2026-08-01T16:00:00",
    )
    second, _ = build_proposed_posting_history(
        allocations=allocations(), payment_ledger=ledger(),
        existing_history=empty_history(), created_at="2026-08-02T16:00:00",
    )
    assert list(first["posting_line_id"]) == list(second["posting_line_id"])
    assert list(first["posting_group_id"]) == list(second["posting_group_id"])

def test_existing_lines_are_not_proposed_again():
    first, _ = build_proposed_posting_history(
        allocations=allocations(), payment_ledger=ledger(),
        existing_history=empty_history(), created_at="2026-08-01T16:00:00",
    )
    second, diagnostics = build_proposed_posting_history(
        allocations=allocations(), payment_ledger=ledger(),
        existing_history=first, created_at="2026-08-02T16:00:00",
    )
    assert second.empty
    assert set(diagnostics["diagnostic_type"]) == {"Already In Posting History"}

def test_duplicate_history_ids_are_rejected():
    history = pd.DataFrame([{c:"" for c in POSTING_HISTORY_COLUMNS} for _ in range(2)])
    history["posting_line_id"] = "pl_duplicate"
    try:
        validate_posting_history(history)
    except ValueError as exc:
        assert "Duplicate posting_line_id" in str(exc)
    else:
        raise AssertionError("Duplicate posting IDs were not rejected.")
