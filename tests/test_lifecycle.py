from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.reconciliation.engine import build_reconciliation


def reservation() -> pd.DataFrame:
    return pd.DataFrame([{
        "reservation_id": "r1",
        "channel_reservation_id": "",
        "guest": "Guest",
        "listing": "Room",
        "property_class": "Motel",
        "source": "website",
        "payment_method": "STRIPE",
        "confirmation_date": pd.Timestamp("2026-01-01"),
        "check_in": pd.Timestamp("2026-01-05"),
        "check_out": pd.Timestamp("2026-01-07"),
        "income_account": "Motel Rent - Short Term",
        "total_paid": 100.0,
        "total_refunded": 0.0,
        "balance_due": 0.0,
    }])


def matches() -> pd.DataFrame:
    return pd.DataFrame([{
        "reconciliation_id": "DSRL-R-0001",
        "match_status": "Exact Match",
        "match_method": "Guesty Reservation ID",
        "confidence_score": 100,
    }])


def processors() -> pd.DataFrame:
    return pd.DataFrame([{
        "reservation_id": "r1",
        "channel_reservation_id": "",
        "transaction_type": "charge",
        "gross_amount": 100.0,
    }])


def payments(
    payout_status: str = "Assigned",
    payout_id: str = "po1",
) -> pd.DataFrame:
    return pd.DataFrame([{
        "reservation_id": "r1",
        "channel_reservation_id": "",
        "payout_assignment_status": payout_status,
        "payout_id": payout_id,
    }])


def payouts(
    allocation: str = "Fully Allocated",
    bank_status: str = "Matched",
) -> pd.DataFrame:
    return pd.DataFrame([{
        "payout_id": "po1",
        "transaction_date": pd.Timestamp("2026-01-08"),
        "allocation_status": allocation,
        "bank_match_status": bank_status,
        "bank_transaction_id": (
            "bank1" if bank_status == "Matched" else ""
        ),
        "bank_transaction_date": (
            pd.Timestamp("2026-01-08")
            if bank_status == "Matched"
            else pd.NaT
        ),
    }])


def overrides(tmp_path: Path) -> Path:
    path = tmp_path / "overrides.csv"
    path.write_text(
        "reservation_id,channel_reservation_id,"
        "override_type,effective_date,amount,"
        "notes,status\n",
        encoding="utf-8",
    )
    return path


def test_fully_reconciled(tmp_path: Path) -> None:
    result = build_reconciliation(
        reservation(),
        matches(),
        processors(),
        payments(),
        payouts(),
        overrides(tmp_path),
        acquisition_date="2025-10-01",
        as_of_date="2026-08-01",
    )

    assert (
        result.loc[0, "lifecycle_status"]
        == "Fully Reconciled"
    )
    assert result.loc[0, "review_required"] == "No"


def test_payout_allocation_review(
    tmp_path: Path,
) -> None:
    result = build_reconciliation(
        reservation(),
        matches(),
        processors(),
        payments(),
        payouts(allocation="Difference"),
        overrides(tmp_path),
        acquisition_date="2025-10-01",
        as_of_date="2026-08-01",
    )

    assert (
        result.loc[0, "lifecycle_status"]
        == "Payout Allocation Review"
    )
    assert result.loc[0, "review_required"] == "Yes"


def test_deposit_missing(tmp_path: Path) -> None:
    result = build_reconciliation(
        reservation(),
        matches(),
        processors(),
        payments(),
        payouts(bank_status="Unmatched"),
        overrides(tmp_path),
        acquisition_date="2025-10-01",
        as_of_date="2026-08-01",
    )

    assert (
        result.loc[0, "lifecycle_status"]
        == "Deposit Missing or Review"
    )


def test_pending_payout_is_not_error(
    tmp_path: Path,
) -> None:
    result = build_reconciliation(
        reservation(),
        matches(),
        processors(),
        payments(
            payout_status="Pending Future Payout",
            payout_id="",
        ),
        payouts(),
        overrides(tmp_path),
        acquisition_date="2025-10-01",
        as_of_date="2026-08-01",
    )

    assert (
        result.loc[0, "lifecycle_status"]
        == "Payout Pending"
    )
    assert result.loc[0, "review_required"] == "No"
