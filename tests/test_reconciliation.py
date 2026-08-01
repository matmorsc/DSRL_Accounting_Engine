from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.reconciliation.engine import build_reconciliation


def _reservation(
    *,
    reservation_id: str = "r1",
    channel_id: str = "",
    source: str = "website",
    payment_method: str = "STRIPE",
    check_in: str = "2026-07-01",
    check_out: str = "2026-07-03",
    total_paid: float = 100.0,
    refunded: float = 0.0,
    balance_due: float = 0.0,
) -> dict[str, object]:
    return {
        "reservation_id": reservation_id,
        "channel_reservation_id": channel_id,
        "guest": "Test Guest",
        "listing": "DSRL Lodge Room 5",
        "property_class": "Motel",
        "source": source,
        "payment_method": payment_method,
        "confirmation_date": pd.Timestamp("2026-06-01"),
        "check_in": pd.Timestamp(check_in),
        "check_out": pd.Timestamp(check_out),
        "income_account": "Motel Rent - Short Term",
        "total_paid": total_paid,
        "total_refunded": refunded,
        "balance_due": balance_due,
    }


def _match(
    status: str = "Exact Match",
) -> dict[str, object]:
    return {
        "reconciliation_id": "DSRL-R-0001",
        "match_status": status,
        "match_method": "Guesty Reservation ID",
        "confidence_score": 100,
    }


def _processor(
    *,
    reservation_id: str = "r1",
    transaction_type: str = "charge",
    amount: float = 100.0,
) -> dict[str, object]:
    return {
        "reservation_id": reservation_id,
        "channel_reservation_id": "",
        "transaction_type": transaction_type,
        "gross_amount": amount,
    }


def _empty_overrides(tmp_path: Path) -> Path:
    path = tmp_path / "overrides.csv"
    path.write_text(
        "reservation_id,channel_reservation_id,"
        "override_type,effective_date,amount,"
        "notes,status\n",
        encoding="utf-8",
    )
    return path


def test_future_airbnb_is_expected(
    tmp_path: Path,
) -> None:
    reservations = pd.DataFrame(
        [
            _reservation(
                channel_id="HM123",
                source="airbnb2",
                payment_method="AIRBNB",
                check_in="2026-08-05",
                check_out="2026-08-07",
                total_paid=0.0,
            )
        ]
    )
    matches = pd.DataFrame(
        [_match(status="No Processor Match")]
    )
    processors = pd.DataFrame(
        columns=[
            "reservation_id",
            "channel_reservation_id",
            "transaction_type",
            "gross_amount",
        ]
    )

    result = build_reconciliation(
        reservations,
        matches,
        processors,
        _empty_overrides(tmp_path),
        acquisition_date="2025-10-01",
        as_of_date="2026-08-01",
    )

    assert (
        result.loc[0, "reconciliation_status"]
        == "Expected Future Airbnb Payment"
    )
    assert result.loc[0, "review_required"] == "No"


def test_pre_acquisition_is_outside_scope(
    tmp_path: Path,
) -> None:
    reservations = pd.DataFrame(
        [
            _reservation(
                check_in="2025-08-01",
                check_out="2025-08-05",
                total_paid=0.0,
            )
        ]
    )
    matches = pd.DataFrame(
        [_match(status="No Processor Match")]
    )
    processors = pd.DataFrame(
        columns=[
            "reservation_id",
            "channel_reservation_id",
            "transaction_type",
            "gross_amount",
        ]
    )

    result = build_reconciliation(
        reservations,
        matches,
        processors,
        _empty_overrides(tmp_path),
        acquisition_date="2025-10-01",
        as_of_date="2026-08-01",
    )

    assert (
        result.loc[0, "reconciliation_status"]
        == "Outside Reporting Scope"
    )


def test_exact_payment_becomes_processor_matched(
    tmp_path: Path,
) -> None:
    reservations = pd.DataFrame(
        [_reservation(total_paid=100.0)]
    )
    matches = pd.DataFrame([_match()])
    processors = pd.DataFrame(
        [_processor(amount=100.0)]
    )

    result = build_reconciliation(
        reservations,
        matches,
        processors,
        _empty_overrides(tmp_path),
        acquisition_date="2025-10-01",
        as_of_date="2026-08-01",
    )

    assert (
        result.loc[0, "reconciliation_status"]
        == "Processor Matched"
    )
    assert result.loc[0, "review_required"] == "No"


def test_override_replaces_automatic_status(
    tmp_path: Path,
) -> None:
    reservations = pd.DataFrame(
        [_reservation(total_paid=100.0)]
    )
    matches = pd.DataFrame(
        [_match(status="No Processor Match")]
    )
    processors = pd.DataFrame(
        columns=[
            "reservation_id",
            "channel_reservation_id",
            "transaction_type",
            "gross_amount",
        ]
    )

    override_path = tmp_path / "overrides.csv"
    override_path.write_text(
        "reservation_id,channel_reservation_id,"
        "override_type,effective_date,amount,"
        "notes,status\n"
        "r1,,Approved Refund,2026-07-01,100,"
        "Guest refunded,Active\n",
        encoding="utf-8",
    )

    result = build_reconciliation(
        reservations,
        matches,
        processors,
        override_path,
        acquisition_date="2025-10-01",
        as_of_date="2026-08-01",
    )

    assert (
        result.loc[0, "reconciliation_status"]
        == "Approved Refund"
    )
    assert result.loc[0, "review_required"] == "No"
