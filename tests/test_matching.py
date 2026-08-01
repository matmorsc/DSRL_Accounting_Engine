from __future__ import annotations

import pandas as pd

from src.matching.engine import build_matches


def _reservation(
    reservation_id: str = "",
    channel_id: str = "",
    payment_method: str = "STRIPE",
    total_paid: float = 100.0,
) -> dict[str, object]:
    return {
        "reservation_id": reservation_id,
        "channel_reservation_id": channel_id,
        "guest": "Test Guest",
        "listing": "DSRL Lodge Room 5",
        "confirmation_date": pd.Timestamp("2026-01-01"),
        "check_in": pd.Timestamp("2026-01-05"),
        "payment_method": payment_method,
        "total_paid": total_paid,
        "total_payout": total_paid,
        "accommodation_revenue": total_paid,
    }


def _transaction(
    transaction_id: str,
    account: str,
    reservation_id: str = "",
    channel_id: str = "",
    amount: float = 100.0,
    date: str = "2026-01-01",
) -> dict[str, object]:
    return {
        "processor": "Stripe",
        "processor_account": account,
        "transaction_id": transaction_id,
        "transaction_type": "charge",
        "transaction_date": pd.Timestamp(date),
        "gross_amount": amount,
        "net_amount": amount - 3.0,
        "reservation_id": reservation_id,
        "channel_reservation_id": channel_id,
    }


def test_matches_by_guesty_reservation_id() -> None:
    reservations = pd.DataFrame(
        [_reservation(reservation_id="guesty-1")]
    )
    transactions = pd.DataFrame(
        [
            _transaction(
                "txn-1",
                "Main Guesty",
                reservation_id="guesty-1",
            )
        ]
    )

    matches = build_matches(
        reservations,
        transactions,
    )

    assert matches.loc[0, "match_status"] == "Exact Match"
    assert (
        matches.loc[0, "match_method"]
        == "Guesty Reservation ID"
    )
    assert matches.loc[0, "confidence_score"] == 100


def test_matches_by_channel_id() -> None:
    reservations = pd.DataFrame(
        [_reservation(channel_id="AIRBNB-1")]
    )
    transactions = pd.DataFrame(
        [
            _transaction(
                "AIRBNB-1",
                "Airbnb",
                channel_id="AIRBNB-1",
            )
        ]
    )

    matches = build_matches(
        reservations,
        transactions,
    )

    assert matches.loc[0, "match_status"] == "Exact Match"
    assert (
        matches.loc[0, "match_method"]
        == "Channel Reservation ID"
    )
    assert matches.loc[0, "confidence_score"] == 98


def test_proposes_single_legacy_candidate() -> None:
    reservations = pd.DataFrame(
        [_reservation(total_paid=650.0)]
    )
    transactions = pd.DataFrame(
        [
            _transaction(
                "legacy-1",
                "Legacy Cognito",
                amount=650.0,
                date="2026-01-03",
            )
        ]
    )

    matches = build_matches(
        reservations,
        transactions,
    )

    assert (
        matches.loc[0, "match_status"]
        == "Single Legacy Candidate"
    )
    assert matches.loc[0, "candidate_count"] == 1
    assert matches.loc[0, "review_required"] == "Yes"


def test_does_not_force_unmatched_reservation() -> None:
    reservations = pd.DataFrame(
        [_reservation(total_paid=250.0)]
    )
    transactions = pd.DataFrame(
        [
            _transaction(
                "legacy-1",
                "Legacy Cognito",
                amount=650.0,
            )
        ]
    )

    matches = build_matches(
        reservations,
        transactions,
    )

    assert (
        matches.loc[0, "match_status"]
        == "No Processor Match"
    )
    assert matches.loc[0, "confidence_score"] == 0
