from __future__ import annotations

import pandas as pd

from src.reconciliation.stripe_charge_classification import (
    build_charge_classification_ledger,
)
from src.posting.stripe_historical_allocations import (
    build_stripe_historical_allocations,
)


def rules():
    return {
        "classes": {
            "Motel": "Hospitality",
            "tax": "Hospitality",
        },
        "accounts": {
            "tax_payable": "Sales & Lodging Taxes Payable",
        },
        "tax_descriptions": {
            "state_tax": "State",
            "county_tax": "County",
            "local_tax": "Local",
        },
    }


def reservations():
    return pd.DataFrame([{
        "reservation_id": "r1",
        "channel_reservation_id": "G1",
        "guest": "Guest",
        "listing": "Room 5",
        "property_class": "Motel",
        "income_account": "Motel Rent - Short Term",
        "accommodation_revenue": 100.0,
        "state_tax": 5.0,
        "county_tax": 0.0,
        "local_tax": 4.09,
    }])


def payment_ledger():
    return pd.DataFrame([
        {
            "payment_event_id": "Main::charge",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_charge",
            "transaction_type": "charge",
            "source_id": "ch_1",
            "gross_amount": 109.09,
            "reservation_id": "r1",
            "channel_reservation_id": "G1",
            "guest": "Guest",
            "listing": "Room 5",
            "payout_id": "po_old",
        },
        {
            "payment_event_id": "Main::refund",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_refund",
            "transaction_type": "refund",
            "source_id": "ch_1",
            "gross_amount": -54.54,
            "reservation_id": "r1",
            "channel_reservation_id": "G1",
            "guest": "Guest",
            "listing": "Room 5",
            "payout_id": "po_target",
        },
    ])


def test_charge_classification_is_built():
    ledger, diagnostics = (
        build_charge_classification_ledger(
            payment_ledger=payment_ledger(),
            reservations=reservations(),
            existing_ledger=pd.DataFrame(
                columns=[
                    "processor_account",
                    "source_id",
                    "charge_transaction_id",
                    "reservation_id",
                    "channel_reservation_id",
                    "guest",
                    "listing",
                    "property_class",
                    "income_account",
                    "qb_class",
                    "revenue_share",
                    "state_tax_share",
                    "county_tax_share",
                    "local_tax_share",
                    "classification_status",
                    "classification_source",
                    "notes",
                ]
            ),
            rules=rules(),
        )
    )

    assert len(ledger) == 1
    assert ledger.loc[0, "source_id"] == "ch_1"
    assert ledger.loc[0, "income_account"] == (
        "Motel Rent - Short Term"
    )
    assert diagnostics.empty


def test_refund_reuses_charge_classification():
    classification, _ = (
        build_charge_classification_ledger(
            payment_ledger=payment_ledger(),
            reservations=reservations(),
            existing_ledger=pd.DataFrame(
                columns=[
                    "processor_account",
                    "source_id",
                    "charge_transaction_id",
                    "reservation_id",
                    "channel_reservation_id",
                    "guest",
                    "listing",
                    "property_class",
                    "income_account",
                    "qb_class",
                    "revenue_share",
                    "state_tax_share",
                    "county_tax_share",
                    "local_tax_share",
                    "classification_status",
                    "classification_source",
                    "notes",
                ]
            ),
            rules=rules(),
        )
    )

    allocations, diagnostics = (
        build_stripe_historical_allocations(
            payment_ledger=payment_ledger(),
            charge_classification_ledger=classification,
            already_allocated_event_ids={"Main::charge"},
            rules=rules(),
        )
    )

    assert round(allocations["amount"].sum(), 2) == -54.54
    assert set(allocations["account"]) == {
        "Motel Rent - Short Term",
        "Sales & Lodging Taxes Payable",
    }
    assert diagnostics.empty
