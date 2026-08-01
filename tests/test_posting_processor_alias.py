from __future__ import annotations

import pandas as pd

from src.posting.engine import build_posting_status


def _payouts() -> pd.DataFrame:
    return pd.DataFrame([{
        "payout_id": "po1",
        "processor": "Stripe",
        "processor_account": "Main Guesty",
        "transaction_date": pd.Timestamp("2026-06-01"),
        "payout_amount": 100.0,
        "bank_transaction_id": "bank1",
        "bank_transaction_date": pd.Timestamp("2026-06-01"),
        "bank_amount": 100.0,
        "bank_match_status": "Matched",
    }])


def _gl() -> pd.DataFrame:
    return pd.DataFrame([{
        "account": "Motel Rent - Short Term",
        "transaction_date": pd.Timestamp("2026-06-01"),
        "transaction_type": "Deposit",
        "number": "123",
        "name": "",
        "memo": "ACH Deposit STRIPE",
        "split_account": "Business Checking",
        "amount": 100.0,
        "identified_processor": "Stripe",
        "is_income_account": True,
        "is_bank_deposit": True,
    }])


def _batches_with_identified_processor() -> pd.DataFrame:
    return pd.DataFrame([{
        "batch_id": "QB-BATCH-001",
        "transaction_date": pd.Timestamp("2026-06-01"),
        "identified_processor": "Stripe",
        "gross_posted_amount": 100.0,
        "processor_fee_amount": 0.0,
        "net_posted_amount": 100.0,
        "transaction_count": 1,
        "quickbooks_reference": "123",
    }])


def _batches_with_processor() -> pd.DataFrame:
    return pd.DataFrame([{
        "batch_id": "QB-BATCH-001",
        "transaction_date": pd.Timestamp("2026-06-01"),
        "processor": "Stripe",
        "gross_posted_amount": 100.0,
        "processor_fee_amount": 0.0,
        "net_posted_amount": 100.0,
        "transaction_count": 1,
        "quickbooks_reference": "123",
    }])


def _overrides(tmp_path):
    path = tmp_path / "posting_overrides.csv"
    path.write_text(
        "payout_id,bank_transaction_id,posting_status,"
        "quickbooks_reference,notes\n",
        encoding="utf-8",
    )
    return path


def test_accepts_identified_processor_column(tmp_path) -> None:
    result = build_posting_status(
        payout_ledger=_payouts(),
        quickbooks_gl=_gl(),
        quickbooks_batches=_batches_with_identified_processor(),
        posting_overrides_path=_overrides(tmp_path),
        assume_posted_through="2026-05-15",
    )

    assert result.loc[0, "posting_status"] == "Already Posted"


def test_accepts_processor_column(tmp_path) -> None:
    result = build_posting_status(
        payout_ledger=_payouts(),
        quickbooks_gl=_gl(),
        quickbooks_batches=_batches_with_processor(),
        posting_overrides_path=_overrides(tmp_path),
        assume_posted_through="2026-05-15",
    )

    assert result.loc[0, "posting_status"] == "Already Posted"
