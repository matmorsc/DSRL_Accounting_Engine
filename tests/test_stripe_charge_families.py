from __future__ import annotations

import pandas as pd

from src.reconciliation.stripe_charge_families import (
    apply_family_metadata_to_payment_ledger,
    build_stripe_charge_families,
    summarize_stripe_charge_families,
)
from src.reconciliation.stripe_family_assignment import (
    assign_stripe_families_to_payouts,
)


def stripe_rows():
    return pd.DataFrame([
        {
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_charge",
            "transaction_type": "charge",
            "source_id": "ch_1",
            "transaction_date": "2026-07-01",
            "available_date": "2026-07-03",
            "gross_amount": 100.00,
            "processor_fee": 3.00,
            "net_amount": 97.00,
            "reservation_id": "r1",
            "channel_reservation_id": "",
            "guest": "Guest",
            "listing": "Room 1",
            "source_file": "stripe.csv",
        },
        {
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_refund",
            "transaction_type": "refund",
            "source_id": "ch_1",
            "transaction_date": "2026-07-07",
            "available_date": "2026-07-07",
            "gross_amount": -54.54,
            "processor_fee": 0.00,
            "net_amount": -54.54,
            "reservation_id": "",
            "channel_reservation_id": "",
            "guest": "",
            "listing": "",
            "source_file": "stripe.csv",
        },
        {
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_adjustment",
            "transaction_type": "adjustment",
            "source_id": "ch_1",
            "transaction_date": "2026-07-07",
            "available_date": "2026-07-07",
            "gross_amount": 0.22,
            "processor_fee": 0.00,
            "net_amount": 0.22,
            "reservation_id": "",
            "channel_reservation_id": "",
            "guest": "",
            "listing": "",
            "source_file": "stripe.csv",
        },
    ])


def test_family_inherits_charge_metadata():
    result, diagnostics = build_stripe_charge_families(
        stripe_rows()
    )

    refund = result.loc[
        result["transaction_id"].eq("txn_refund")
    ].iloc[0]

    assert refund["charge_family_id"] == "ch_1"
    assert refund["family_reservation_id"] == "r1"
    assert refund["family_guest"] == "Guest"
    assert refund["family_metadata_inherited"] == "Yes"
    assert diagnostics.empty


def test_family_summary_preserves_net_effect():
    result, _ = build_stripe_charge_families(
        stripe_rows()
    )
    summary = summarize_stripe_charge_families(result)

    assert len(summary) == 1
    assert summary.loc[0, "family_event_count"] == 3
    assert summary.loc[0, "family_net"] == 42.68
    assert summary.loc[0, "event_types"] == (
        "adjustment | charge | refund"
    )


def test_family_assignment_keeps_components_together():
    transactions, _ = build_stripe_charge_families(
        stripe_rows()
    )

    payments = transactions.copy()
    payments["payment_event_id"] = (
        payments["processor_account"]
        + "::"
        + payments["transaction_id"]
    )
    payments["payout_id"] = ""
    payments["payout_assignment_status"] = "Unassigned"
    payments["payout_assignment_method"] = ""
    payments["payout_date"] = pd.NaT

    payouts = pd.DataFrame([
        {
            "payout_id": "po_early",
            "processor_account": "Main Guesty",
            "transaction_date": "2026-07-05",
        },
        {
            "payout_id": "po_late",
            "processor_account": "Main Guesty",
            "transaction_date": "2026-07-08",
        },
    ])

    result = assign_stripe_families_to_payouts(
        payments,
        payouts,
    )

    assert set(result["payout_id"]) == {"po_late"}
    assert set(result["payout_assignment_status"]) == {
        "Assigned"
    }


def test_payment_ledger_receives_family_metadata():
    transactions, _ = build_stripe_charge_families(
        stripe_rows()
    )

    ledger = transactions[
        [
            "transaction_id",
            "reservation_id",
            "channel_reservation_id",
            "guest",
            "listing",
            "family_reservation_id",
            "family_channel_reservation_id",
            "family_guest",
            "family_listing",
        ]
    ].copy()

    result = apply_family_metadata_to_payment_ledger(
        ledger
    )

    refund = result.loc[
        result["transaction_id"].eq("txn_refund")
    ].iloc[0]

    assert refund["reservation_id"] == "r1"
    assert refund["guest"] == "Guest"
