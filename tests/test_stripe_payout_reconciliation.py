from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.importers.stripe_payout_reconciliation import (
    normalize_payout_reconciliation,
)
from src.reconciliation.stripe_payout_membership import (
    apply_exact_stripe_payout_membership,
)


def report_file(tmp_path: Path) -> Path:
    path = tmp_path / "report.csv"
    pd.DataFrame([
        {
            "account_id": "acct_1",
            "account_name": "DSRL - Guesty",
            "automatic_payout_id": "po_target",
            "automatic_payout_effective_at": (
                "2026-07-10 00:00:00"
            ),
            "balance_transaction_id": "txn_refund",
            "created": "2026-07-07 23:20:00",
            "available_on": "2026-07-07 23:20:00",
            "currency": "usd",
            "gross": -54.54,
            "fee": 0.0,
            "net": -54.54,
            "reporting_category": "refund",
            "description": "REFUND FOR CHARGE",
        },
        {
            "account_id": "acct_1",
            "account_name": "DSRL - Guesty",
            "automatic_payout_id": "po_target",
            "automatic_payout_effective_at": (
                "2026-07-10 00:00:00"
            ),
            "balance_transaction_id": "txn_adjustment",
            "created": "2026-07-07 23:20:00",
            "available_on": "2026-07-07 23:20:00",
            "currency": "usd",
            "gross": 0.22,
            "fee": 0.0,
            "net": 0.22,
            "reporting_category": "fee",
            "description": "Application fee refund",
        },
    ]).to_csv(path, index=False)
    return path


def test_report_normalizes_exact_membership(tmp_path: Path):
    result = normalize_payout_reconciliation(
        [report_file(tmp_path)],
        account_mapping={
            "DSRL - Guesty": "Main Guesty",
        },
    )

    assert len(result) == 2
    assert set(result["payout_id"]) == {"po_target"}
    assert set(result["processor_account"]) == {
        "Main Guesty"
    }


def test_exact_membership_replaces_date_guess(
    tmp_path: Path,
):
    membership = normalize_payout_reconciliation(
        [report_file(tmp_path)],
        account_mapping={
            "DSRL - Guesty": "Main Guesty",
        },
    )

    ledger = pd.DataFrame([
        {
            "payment_event_id": "Main::txn_refund",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_refund",
            "net_amount": -54.54,
            "payout_id": "po_wrong",
            "payout_assignment_status": "Assigned",
            "payout_assignment_method": "Date fallback",
            "payout_date": "2026-07-07",
        },
        {
            "payment_event_id": "Main::txn_adjustment",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_adjustment",
            "net_amount": 0.22,
            "payout_id": "po_wrong",
            "payout_assignment_status": "Assigned",
            "payout_assignment_method": "Date fallback",
            "payout_date": "2026-07-07",
        },
    ])

    result, diagnostics = (
        apply_exact_stripe_payout_membership(
            ledger,
            membership,
        )
    )

    assert set(result["payout_id"]) == {"po_target"}
    assert set(
        result["payout_assignment_method"]
    ) == {"Exact Stripe payout reconciliation"}
    assert set(
        diagnostics["assignment_changed"]
    ) == {"Yes"}


def test_uncovered_event_keeps_fallback_assignment(
    tmp_path: Path,
):
    membership = normalize_payout_reconciliation(
        [report_file(tmp_path)],
        account_mapping={
            "DSRL - Guesty": "Main Guesty",
        },
    )

    ledger = pd.DataFrame([
        {
            "payment_event_id": "Main::txn_other",
            "processor": "Stripe",
            "processor_account": "Main Guesty",
            "transaction_id": "txn_other",
            "net_amount": 97.0,
            "payout_id": "po_existing",
            "payout_assignment_status": "Assigned",
            "payout_assignment_method": "Date fallback",
            "payout_date": "2026-07-05",
        }
    ])

    result, diagnostics = (
        apply_exact_stripe_payout_membership(
            ledger,
            membership,
        )
    )

    assert result.loc[0, "payout_id"] == "po_existing"
    assert (
        result.loc[0, "payout_assignment_method"]
        == "Date fallback"
    )
    assert diagnostics.empty
