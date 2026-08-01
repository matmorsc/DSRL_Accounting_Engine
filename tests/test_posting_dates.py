from __future__ import annotations

import pandas as pd

from src.posting.engine import build_posting_status


def empty_overrides(tmp_path):
    path = tmp_path / "posting_overrides.csv"
    path.write_text(
        "payout_id,bank_transaction_id,posting_status,"
        "quickbooks_reference,notes\n",
        encoding="utf-8",
    )
    return path


def test_missing_payout_date_needs_review(
    tmp_path,
) -> None:
    payouts = pd.DataFrame([{
        "payout_id": "po_missing",
        "processor": "Stripe",
        "processor_account": "Main Guesty",
        "transaction_date": pd.NaT,
        "payout_amount": 100.0,
        "bank_transaction_id": "",
        "bank_transaction_date": pd.NaT,
        "bank_amount": 0.0,
        "bank_match_status": "Unmatched",
    }])

    quickbooks = pd.DataFrame([{
        "account": "Motel Rent - Short Term",
        "transaction_date": pd.Timestamp("2026-06-01"),
        "transaction_type": "Deposit",
        "number": "",
        "name": "",
        "memo": "ACH Deposit STRIPE",
        "split_account": "Business Checking",
        "amount": 100.0,
        "identified_processor": "Stripe",
        "is_income_account": True,
        "is_bank_deposit": True,
    }])

    result = build_posting_status(
        payout_ledger=payouts,
        quickbooks_gl=quickbooks,
        posting_overrides_path=empty_overrides(tmp_path),
        assume_posted_through="2026-05-15",
    )

    assert result.loc[0, "posting_status"] == "Needs Review"
    assert result.loc[0, "generate_entry"] == "No"
    assert result.loc[0, "posting_match_method"] == "Payout date missing"
