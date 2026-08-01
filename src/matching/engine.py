from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


PAYMENT_TYPES = {"charge", "payment", "reservation", "refund"}


@dataclass(frozen=True)
class Candidate:
    transaction_id: str
    processor_account: str
    transaction_type: str
    transaction_date: pd.Timestamp | None
    gross_amount: float
    net_amount: float
    score: int
    reason: str


def _norm(value: object) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if text.lower() == "nan":
        return ""

    return text


def _date_distance_days(
    left: object,
    right: object,
) -> int | None:
    left_date = pd.to_datetime(left, errors="coerce")
    right_date = pd.to_datetime(right, errors="coerce")

    if pd.isna(left_date) or pd.isna(right_date):
        return None

    return abs((left_date.normalize() - right_date.normalize()).days)


def _amount_candidates(row: pd.Series) -> list[float]:
    values = [
        row.get("total_paid", 0.0),
        row.get("total_payout", 0.0),
        row.get("accommodation_revenue", 0.0),
    ]

    return [
        round(abs(float(value)), 2)
        for value in values
        if pd.notna(value)
    ]


def _amount_matches(
    reservation: pd.Series,
    transaction: pd.Series,
    tolerance: float,
) -> bool:
    transaction_amounts = [
        round(abs(float(transaction.get("gross_amount", 0.0))), 2),
        round(abs(float(transaction.get("net_amount", 0.0))), 2),
    ]

    reservation_amounts = _amount_candidates(reservation)

    return any(
        abs(transaction_amount - reservation_amount) <= tolerance
        for transaction_amount in transaction_amounts
        for reservation_amount in reservation_amounts
    )


def _legacy_candidates(
    reservation: pd.Series,
    processor_transactions: pd.DataFrame,
    amount_tolerance: float,
) -> list[Candidate]:
    legacy = processor_transactions.loc[
        processor_transactions["processor_account"].isin(
            ["Legacy Cognito", "Legacy Keycheck"]
        )
        & processor_transactions["transaction_type"].isin(
            ["charge", "payment", "refund"]
        )
    ].copy()

    candidates: list[Candidate] = []

    for _, transaction in legacy.iterrows():
        if not _amount_matches(
            reservation,
            transaction,
            tolerance=amount_tolerance,
        ):
            continue

        confirmation_distance = _date_distance_days(
            reservation.get("confirmation_date"),
            transaction.get("transaction_date"),
        )

        check_in_distance = _date_distance_days(
            reservation.get("check_in"),
            transaction.get("transaction_date"),
        )

        timing_ok = False
        timing_reason = ""

        if (
            confirmation_distance is not None
            and confirmation_distance <= 10
        ):
            timing_ok = True
            timing_reason = (
                f"exact amount and transaction within "
                f"{confirmation_distance} days of confirmation"
            )

        elif (
            check_in_distance is not None
            and check_in_distance <= 2
        ):
            timing_ok = True
            timing_reason = (
                f"exact amount and transaction within "
                f"{check_in_distance} days of check-in"
            )

        if not timing_ok:
            continue

        score = 80

        if confirmation_distance is not None:
            score -= min(confirmation_distance, 10)

        if (
            check_in_distance is not None
            and check_in_distance <= 2
        ):
            score += 3

        candidates.append(
            Candidate(
                transaction_id=_norm(
                    transaction.get("transaction_id")
                ),
                processor_account=_norm(
                    transaction.get("processor_account")
                ),
                transaction_type=_norm(
                    transaction.get("transaction_type")
                ),
                transaction_date=pd.to_datetime(
                    transaction.get("transaction_date"),
                    errors="coerce",
                ),
                gross_amount=float(
                    transaction.get("gross_amount", 0.0)
                ),
                net_amount=float(
                    transaction.get("net_amount", 0.0)
                ),
                score=max(min(score, 85), 65),
                reason=timing_reason,
            )
        )

    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate.score,
            candidate.transaction_date
            if pd.notna(candidate.transaction_date)
            else pd.Timestamp.max,
            candidate.transaction_id,
        ),
    )


def _exact_matches(
    reservation: pd.Series,
    processor_transactions: pd.DataFrame,
) -> tuple[pd.DataFrame, str, int]:
    reservation_id = _norm(
        reservation.get("reservation_id")
    )
    channel_id = _norm(
        reservation.get("channel_reservation_id")
    )

    if reservation_id:
        by_reservation_id = processor_transactions.loc[
            processor_transactions["reservation_id"]
            .astype(str)
            .str.strip()
            .eq(reservation_id)
            & processor_transactions["transaction_type"].isin(
                PAYMENT_TYPES
            )
        ]

        if not by_reservation_id.empty:
            return (
                by_reservation_id,
                "Guesty Reservation ID",
                100,
            )

    if channel_id:
        by_channel_id = processor_transactions.loc[
            processor_transactions["channel_reservation_id"]
            .astype(str)
            .str.strip()
            .eq(channel_id)
            & processor_transactions["transaction_type"].isin(
                PAYMENT_TYPES
            )
        ]

        if not by_channel_id.empty:
            return (
                by_channel_id,
                "Channel Reservation ID",
                98,
            )

    return (
        processor_transactions.iloc[0:0],
        "",
        0,
    )


def _format_ids(values: Iterable[object]) -> str:
    cleaned = sorted(
        {
            _norm(value)
            for value in values
            if _norm(value)
        }
    )

    return " | ".join(cleaned)


def build_matches(
    reservations: pd.DataFrame,
    processor_transactions: pd.DataFrame,
    amount_tolerance: float = 0.02,
) -> pd.DataFrame:
    required_reservation_columns = {
        "reservation_id",
        "channel_reservation_id",
        "guest",
        "listing",
        "confirmation_date",
        "check_in",
        "payment_method",
        "total_paid",
        "total_payout",
        "accommodation_revenue",
    }

    required_processor_columns = {
        "processor",
        "processor_account",
        "transaction_id",
        "transaction_type",
        "transaction_date",
        "gross_amount",
        "net_amount",
        "reservation_id",
        "channel_reservation_id",
    }

    missing_reservations = sorted(
        required_reservation_columns.difference(
            reservations.columns
        )
    )

    missing_processor = sorted(
        required_processor_columns.difference(
            processor_transactions.columns
        )
    )

    if missing_reservations:
        raise ValueError(
            f"Normalized reservations missing columns: "
            f"{missing_reservations}"
        )

    if missing_processor:
        raise ValueError(
            f"Normalized processor data missing columns: "
            f"{missing_processor}"
        )

    rows: list[dict[str, object]] = []

    for index, reservation in reservations.iterrows():
        exact, method, confidence = _exact_matches(
            reservation,
            processor_transactions,
        )

        if not exact.empty:
            rows.append(
                {
                    "reconciliation_id": (
                        f"DSRL-R-{index + 1:04d}"
                    ),
                    "reservation_id": _norm(
                        reservation.get("reservation_id")
                    ),
                    "channel_reservation_id": _norm(
                        reservation.get(
                            "channel_reservation_id"
                        )
                    ),
                    "guest": _norm(
                        reservation.get("guest")
                    ),
                    "listing": _norm(
                        reservation.get("listing")
                    ),
                    "payment_method": _norm(
                        reservation.get("payment_method")
                    ),
                    "match_status": "Exact Match",
                    "match_method": method,
                    "confidence_score": confidence,
                    "matched_transaction_count": len(exact),
                    "matched_processor_accounts": _format_ids(
                        exact["processor_account"]
                    ),
                    "matched_transaction_ids": _format_ids(
                        exact["transaction_id"]
                    ),
                    "candidate_count": 0,
                    "candidate_transaction_ids": "",
                    "candidate_reasons": "",
                    "review_required": "No",
                }
            )
            continue

        legacy_candidates = _legacy_candidates(
            reservation,
            processor_transactions,
            amount_tolerance=amount_tolerance,
        )

        if len(legacy_candidates) == 1:
            candidate = legacy_candidates[0]

            rows.append(
                {
                    "reconciliation_id": (
                        f"DSRL-R-{index + 1:04d}"
                    ),
                    "reservation_id": _norm(
                        reservation.get("reservation_id")
                    ),
                    "channel_reservation_id": _norm(
                        reservation.get(
                            "channel_reservation_id"
                        )
                    ),
                    "guest": _norm(
                        reservation.get("guest")
                    ),
                    "listing": _norm(
                        reservation.get("listing")
                    ),
                    "payment_method": _norm(
                        reservation.get("payment_method")
                    ),
                    "match_status": (
                        "Single Legacy Candidate"
                    ),
                    "match_method": (
                        "Exact amount/date candidate"
                    ),
                    "confidence_score": candidate.score,
                    "matched_transaction_count": 0,
                    "matched_processor_accounts": "",
                    "matched_transaction_ids": "",
                    "candidate_count": 1,
                    "candidate_transaction_ids": (
                        candidate.transaction_id
                    ),
                    "candidate_reasons": (
                        candidate.reason
                    ),
                    "review_required": "Yes",
                }
            )
            continue

        if len(legacy_candidates) > 1:
            rows.append(
                {
                    "reconciliation_id": (
                        f"DSRL-R-{index + 1:04d}"
                    ),
                    "reservation_id": _norm(
                        reservation.get("reservation_id")
                    ),
                    "channel_reservation_id": _norm(
                        reservation.get(
                            "channel_reservation_id"
                        )
                    ),
                    "guest": _norm(
                        reservation.get("guest")
                    ),
                    "listing": _norm(
                        reservation.get("listing")
                    ),
                    "payment_method": _norm(
                        reservation.get("payment_method")
                    ),
                    "match_status": (
                        "Multiple Legacy Candidates"
                    ),
                    "match_method": (
                        "Exact amount/date candidates"
                    ),
                    "confidence_score": max(
                        candidate.score
                        for candidate in legacy_candidates
                    ),
                    "matched_transaction_count": 0,
                    "matched_processor_accounts": "",
                    "matched_transaction_ids": "",
                    "candidate_count": len(
                        legacy_candidates
                    ),
                    "candidate_transaction_ids": (
                        " | ".join(
                            candidate.transaction_id
                            for candidate in legacy_candidates
                        )
                    ),
                    "candidate_reasons": (
                        " | ".join(
                            candidate.reason
                            for candidate in legacy_candidates
                        )
                    ),
                    "review_required": "Yes",
                }
            )
            continue

        rows.append(
            {
                "reconciliation_id": (
                    f"DSRL-R-{index + 1:04d}"
                ),
                "reservation_id": _norm(
                    reservation.get("reservation_id")
                ),
                "channel_reservation_id": _norm(
                    reservation.get(
                        "channel_reservation_id"
                    )
                ),
                "guest": _norm(
                    reservation.get("guest")
                ),
                "listing": _norm(
                    reservation.get("listing")
                ),
                "payment_method": _norm(
                    reservation.get("payment_method")
                ),
                "match_status": "No Processor Match",
                "match_method": "",
                "confidence_score": 0,
                "matched_transaction_count": 0,
                "matched_processor_accounts": "",
                "matched_transaction_ids": "",
                "candidate_count": 0,
                "candidate_transaction_ids": "",
                "candidate_reasons": "",
                "review_required": "Yes",
            }
        )

    output = pd.DataFrame(rows)

    duplicate_reconciliation_ids = output.loc[
        output["reconciliation_id"].duplicated(
            keep=False
        ),
        "reconciliation_id",
    ].unique()

    if len(duplicate_reconciliation_ids):
        raise ValueError(
            "Duplicate reconciliation IDs generated: "
            + ", ".join(
                duplicate_reconciliation_ids[:10]
            )
        )

    return output
