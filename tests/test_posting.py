from __future__ import annotations

import pandas as pd

from src.posting.engine import build_posting_status


def payouts() -> pd.DataFrame:
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


def quickbooks(match: bool = True) -> pd.DataFrame:
    amount = 100.0 if match else 75.0
    return pd.DataFrame([{
        "account": "Motel Rent - Short Term",
        "transaction_date": pd.Timestamp("2026-06-01"),
        "transaction_type": "Deposit",
        "number": "123",
        "name": "",
        "memo": "ACH Deposit STRIPE",
        "split_account": "Business Checking",
        "amount": amount,
        "identified_processor": "Stripe",
        "is_income_account": True,
        "is_bank_deposit": True,
    }])


def empty_overrides(tmp_path):
    path = tmp_path / "posting_overrides.csv"
    path.write_text(
        "payout_id,bank_transaction_id,posting_status,"
        "quickbooks_reference,notes\n",
        encoding="utf-8",
    )
    return path


def test_exact_qb_match_is_already_posted(
    tmp_path,
) -> None:
    result = build_posting_status(
        payout_ledger=payouts(),
        quickbooks_gl=quickbooks(match=True),
        posting_overrides_path=empty_overrides(
            tmp_path
        ),
        assume_posted_through="2026-05-15",
    )

    assert (
        result.loc[0, "posting_status"]
        == "Already Posted"
    )
    assert result.loc[0, "generate_entry"] == "No"


def test_after_cutoff_without_qb_match_is_unposted(
    tmp_path,
) -> None:
    result = build_posting_status(
        payout_ledger=payouts(),
        quickbooks_gl=quickbooks(match=False),
        posting_overrides_path=empty_overrides(
            tmp_path
        ),
        assume_posted_through="2026-05-15",
    )

    assert result.loc[0, "posting_status"] == "Unposted"
    assert result.loc[0, "generate_entry"] == "Yes"


def test_before_cutoff_without_qb_match_needs_review(
    tmp_path,
) -> None:
    frame = payouts()
    frame.loc[0, "transaction_date"] = pd.Timestamp(
        "2026-05-01"
    )
    frame.loc[
        0, "bank_transaction_date"
    ] = pd.Timestamp("2026-05-01")

    result = build_posting_status(
        payout_ledger=frame,
        quickbooks_gl=quickbooks(match=False),
        posting_overrides_path=empty_overrides(
            tmp_path
        ),
        assume_posted_through="2026-05-15",
    )

    assert (
        result.loc[0, "posting_status"]
        == "Needs Review"
    )
    assert result.loc[0, "generate_entry"] == "No"


def test_override_can_force_generate_entry(
    tmp_path,
) -> None:
    path = tmp_path / "posting_overrides.csv"
    path.write_text(
        "payout_id,bank_transaction_id,posting_status,"
        "quickbooks_reference,notes\n"
        "po1,,Generate Entry,,Confirmed missing\n",
        encoding="utf-8",
    )

    result = build_posting_status(
        payout_ledger=payouts(),
        quickbooks_gl=quickbooks(match=True),
        posting_overrides_path=path,
        assume_posted_through="2026-05-15",
    )

    assert (
        result.loc[0, "posting_status"]
        == "Generate Entry"
    )
    assert result.loc[0, "generate_entry"] == "Yes"
