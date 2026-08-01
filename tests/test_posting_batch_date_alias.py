from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.posting.engine import build_posting_status


def _overrides(tmp_path: Path) -> Path:
    path = tmp_path / "posting_overrides.csv"
    path.write_text(
        "payout_id,bank_transaction_id,posting_status,"
        "quickbooks_reference,notes\n",
        encoding="utf-8",
    )
    return path


def test_accepts_batch_date_and_qb_batch_id(
    tmp_path: Path,
) -> None:
    payouts = pd.DataFrame([{
        "payout_id": "po1",
        "processor": "Stripe",
        "processor_account": "Main",
        "transaction_date": pd.Timestamp("2025-11-12"),
        "payout_amount": 100.0,
        "bank_transaction_id": "b1",
        "bank_transaction_date": pd.Timestamp("2025-11-12"),
        "bank_amount": 100.0,
        "bank_match_status": "Matched",
    }])

    batches = pd.DataFrame([{
        "qb_batch_id": "QB-1",
        "processor": "Stripe",
        "batch_date": pd.Timestamp("2025-11-12"),
        "gross_inflows": 103.0,
        "processor_fees": -3.0,
        "net_posted_amount": 100.0,
    }])

    result = build_posting_status(
        payout_ledger=payouts,
        quickbooks_gl=pd.DataFrame(),
        quickbooks_batches=batches,
        posting_overrides_path=_overrides(tmp_path),
        assume_posted_through="2026-05-15",
    )

    assert result.loc[0, "posting_status"] == "Already Posted"
    assert result.loc[0, "quickbooks_batch_id"] == "QB-1"


def test_combined_same_day_payouts_match_one_batch(
    tmp_path: Path,
) -> None:
    payouts = pd.DataFrame([
        {
            "payout_id": "po1",
            "processor": "Stripe",
            "processor_account": "Legacy",
            "transaction_date": pd.Timestamp("2025-11-12"),
            "payout_amount": 635.35,
            "bank_transaction_id": "b1",
            "bank_transaction_date": pd.Timestamp("2025-11-12"),
            "bank_amount": 635.35,
            "bank_match_status": "Matched",
        },
        {
            "payout_id": "po2",
            "processor": "Stripe",
            "processor_account": "Main",
            "transaction_date": pd.Timestamp("2025-11-12"),
            "payout_amount": 532.25,
            "bank_transaction_id": "b2",
            "bank_transaction_date": pd.Timestamp("2025-11-12"),
            "bank_amount": 532.25,
            "bank_match_status": "Matched",
        },
    ])

    batches = pd.DataFrame([{
        "qb_batch_id": "QB-STRIPE-2025-11-12",
        "processor": "Stripe",
        "batch_date": pd.Timestamp("2025-11-12"),
        "gross_inflows": 1200.73,
        "processor_fees": -33.13,
        "net_posted_amount": 1167.60,
    }])

    result = build_posting_status(
        payout_ledger=payouts,
        quickbooks_gl=pd.DataFrame(),
        quickbooks_batches=batches,
        posting_overrides_path=_overrides(tmp_path),
        assume_posted_through="2026-05-15",
    )

    assert set(result["posting_status"]) == {"Already Posted"}
    assert set(result["quickbooks_batch_id"]) == {
        "QB-STRIPE-2025-11-12"
    }
