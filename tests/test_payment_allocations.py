from __future__ import annotations

import pandas as pd

from src.posting.payment_allocations import build_payment_allocations
from src.posting.deposit_drafts_v2 import build_deposit_drafts_v2


def rules():
    return {
        "amount_tolerance": 0.02,
        "classes": {
            "Cabin": "Cabins",
            "RV": "RV Sites",
            "Motel": "Hospitality",
            "tax": "Hospitality",
            "fees": "Hospitality",
        },
        "accounts": {
            "tax_payable": "Sales & Lodging Taxes Payable",
        },
        "processor_fee_accounts": {
            "Stripe": "Bank Charges & Fees:Stripe Processing Fees",
            "Airbnb": "",
        },
        "tax_descriptions": {
            "state_tax": "State",
            "county_tax": "County",
            "local_tax": "Local",
        },
        "marketplace_remitted_tax_processors": ["Airbnb"],
    }


def reservations():
    return pd.DataFrame([{
        "reservation_id": "r1",
        "channel_reservation_id": "A1",
        "guest": "Guest",
        "listing": "River Cabin",
        "property_class": "Cabin",
        "income_account": "Cabin Rent - Short-Term",
        "accommodation_revenue": 100.0,
        "state_tax": 5.0,
        "county_tax": 4.0,
        "local_tax": 6.0,
        "total_paid": 115.0,
        "total_refunded": 0.0,
    }])


def payments(processor="Stripe"):
    return pd.DataFrame([{
        "payment_event_id": "evt1",
        "processor": processor,
        "processor_account": "Main",
        "transaction_id": "txn1",
        "transaction_type": (
            "reservation" if processor == "Airbnb" else "charge"
        ),
        "transaction_date": "2026-06-01",
        "gross_amount": 115.0 if processor == "Stripe" else 100.0,
        "processor_fee": 3.0,
        "net_amount": 112.0 if processor == "Stripe" else 97.0,
        "reservation_id": "r1",
        "channel_reservation_id": "A1",
        "payout_id": "po1",
        "payout_assignment_status": "Assigned",
    }])


def posting(bank_amount):
    return pd.DataFrame([{
        "payout_id": "po1",
        "processor": "Stripe",
        "bank_transaction_id": "bank1",
        "bank_transaction_date": "2026-06-01",
        "bank_amount": bank_amount,
        "posting_status": "Unposted",
        "generate_entry": "Yes",
    }])


def payout(bank_amount, processor="Stripe"):
    return pd.DataFrame([{
        "payout_id": "po1",
        "processor": processor,
        "processor_account": "Main",
        "transaction_date": "2026-06-01",
        "payout_amount": bank_amount,
        "bank_transaction_id": "bank1",
        "bank_transaction_date": "2026-06-01",
        "bank_amount": bank_amount,
    }])


def test_direct_event_allocates_exact_gross():
    allocations, diagnostics = build_payment_allocations(
        payment_ledger=payments(),
        reservations=reservations(),
        rules=rules(),
    )

    non_fee = allocations.loc[
        allocations["allocation_type"].ne("Processor Fee")
    ]

    assert round(non_fee["amount"].sum(), 2) == 115.0
    assert round(allocations["amount"].sum(), 2) == 112.0
    assert diagnostics.empty


def test_marketplace_event_excludes_tax():
    allocations, diagnostics = build_payment_allocations(
        payment_ledger=payments(processor="Airbnb"),
        reservations=reservations(),
        rules=rules(),
    )

    assert set(allocations["allocation_type"]) == {
        "Revenue",
        "Processor Fee",
    }
    assert round(allocations["amount"].sum(), 2) == 97.0
    assert "Missing Fee Account" in set(
        diagnostics["diagnostic_type"]
    )


def test_v2_draft_balances_from_allocations():
    allocations, _ = build_payment_allocations(
        payment_ledger=payments(),
        reservations=reservations(),
        rules=rules(),
    )

    summaries, lines = build_deposit_drafts_v2(
        posting_status=posting(112.0),
        payout_ledger=payout(112.0),
        allocations=allocations,
        rules=rules(),
    )

    assert summaries.loc[0, "balanced"] == "Yes"
    assert summaries.loc[0, "draft_status"] == "Ready for Review"
    assert round(lines["amount"].sum(), 2) == 112.0


def test_unlinked_event_is_diagnostic():
    frame = payments()
    frame.loc[0, "reservation_id"] = "missing"
    frame.loc[0, "channel_reservation_id"] = ""

    allocations, diagnostics = build_payment_allocations(
        payment_ledger=frame,
        reservations=reservations(),
        rules=rules(),
    )

    assert allocations.empty
    assert diagnostics.loc[0, "diagnostic_type"] == (
        "Unlinked Payment Event"
    )
