from __future__ import annotations

import pandas as pd

from src.posting.deposit_drafts import build_deposit_drafts


def rules():
    return {
        "amount_tolerance": 0.02,
        "classes": {
            "Cabin": "Cabins",
            "RV": "RV Sites",
            "Motel": "Hospitality",
            "tax": "Hospitality",
            "fees": "Hospitality",
            "refunds": "Hospitality",
        },
        "accounts": {
            "tax_payable": "Sales & Lodging Taxes Payable",
            "refunds": "Refunds",
        },
        "processor_fee_accounts": {
            "Stripe": "Bank Charges & Fees:Stripe Processing Fees",
            "Airbnb": None,
        },
        "tax_descriptions": {
            "state_tax": "State",
            "county_tax": "County",
            "local_tax": "Local",
        },
        "marketplace_remitted_tax_processors": ["Airbnb"],
    }


def posting(bank_amount=112.0, processor="Stripe"):
    return pd.DataFrame([{
        "payout_id": "po1",
        "processor": processor,
        "payout_date": "2026-06-01",
        "payout_amount": bank_amount,
        "bank_transaction_id": "bank1",
        "bank_transaction_date": "2026-06-01",
        "bank_amount": bank_amount,
        "posting_status": "Unposted",
        "generate_entry": "Yes",
    }])


def payout(bank_amount=112.0, processor="Stripe"):
    return pd.DataFrame([{
        "payout_id": "po1",
        "processor": processor,
        "processor_account": "Main Guesty",
        "transaction_date": "2026-06-01",
        "payout_amount": bank_amount,
        "bank_transaction_id": "bank1",
        "bank_transaction_date": "2026-06-01",
        "bank_amount": bank_amount,
    }])


def payments(
    gross=115.0,
    fee=3.0,
    processor="Stripe",
):
    return pd.DataFrame([{
        "payment_event_id": "evt1",
        "processor": processor,
        "processor_account": "Main Guesty",
        "transaction_id": "txn1",
        "transaction_type": "charge" if processor == "Stripe" else "reservation",
        "gross_amount": gross,
        "processor_fee": fee,
        "net_amount": gross - fee,
        "reservation_id": "r1",
        "channel_reservation_id": "A1" if processor == "Airbnb" else "",
        "payout_id": "po1",
        "payout_assignment_status": "Assigned",
    }])


def reservations(
    *,
    accommodation=100.0,
    state=5.0,
    county=4.0,
    local=6.0,
    total_paid=115.0,
):
    return pd.DataFrame([{
        "reservation_id": "r1",
        "channel_reservation_id": "A1",
        "guest": "Guest",
        "listing": "River Cabin",
        "property_class": "Cabin",
        "income_account": "Cabin Rent - Short-Term",
        "accommodation_revenue": accommodation,
        "state_tax": state,
        "county_tax": county,
        "local_tax": local,
        "total_paid": total_paid,
        "total_refunded": 0.0,
    }])


def test_stripe_draft_balances():
    summaries, lines = build_deposit_drafts(
        posting_status=posting(),
        payout_ledger=payout(),
        payment_ledger=payments(),
        reservations=reservations(),
        rules=rules(),
    )

    assert summaries.loc[0, "balanced"] == "Yes"
    assert summaries.loc[0, "draft_status"] == "Ready for Review"
    assert summaries.loc[0, "draft_total"] == 112.0
    assert set(lines["line_type"]) == {
        "Revenue",
        "Tax",
        "Processor Fee",
    }


def test_airbnb_excludes_marketplace_tax():
    summaries, lines = build_deposit_drafts(
        posting_status=posting(
            bank_amount=97.0,
            processor="Airbnb",
        ),
        payout_ledger=payout(
            bank_amount=97.0,
            processor="Airbnb",
        ),
        payment_ledger=payments(
            gross=100.0,
            fee=3.0,
            processor="Airbnb",
        ),
        reservations=reservations(),
        rules=rules(),
    )

    assert "Tax" not in set(lines["line_type"])
    assert summaries.loc[0, "balanced"] == "Yes"
    assert summaries.loc[0, "draft_status"] == "Review Required"
    assert "fee account for Airbnb" in summaries.loc[0, "review_reason"]


def test_only_generate_entry_rows_are_used():
    status = posting()
    status.loc[0, "generate_entry"] = "No"

    summaries, lines = build_deposit_drafts(
        posting_status=status,
        payout_ledger=payout(),
        payment_ledger=payments(),
        reservations=reservations(),
        rules=rules(),
    )

    assert summaries.empty
    assert lines.empty


def test_missing_reservation_link_requires_review():
    payment_frame = payments()
    payment_frame.loc[0, "reservation_id"] = "missing"
    payment_frame.loc[0, "channel_reservation_id"] = ""

    summaries, _ = build_deposit_drafts(
        posting_status=posting(),
        payout_ledger=payout(),
        payment_ledger=payment_frame,
        reservations=reservations(),
        rules=rules(),
    )

    assert summaries.loc[0, "draft_status"] == "Review Required"
    assert "could not be linked" in summaries.loc[0, "review_reason"]
