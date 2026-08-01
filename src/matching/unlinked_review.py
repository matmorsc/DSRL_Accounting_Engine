from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

import pandas as pd


def _text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def _money(value: object) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def _similarity(left: object, right: object) -> float:
    a = _text(left).lower()
    b = _text(right).lower()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _date_distance(
    left: object,
    right: object,
) -> int | None:
    a = pd.to_datetime(left, errors="coerce")
    b = pd.to_datetime(right, errors="coerce")
    if pd.isna(a) or pd.isna(b):
        return None
    return abs((a.normalize() - b.normalize()).days)


def _candidate_score(
    event: pd.Series,
    reservation: pd.Series,
) -> tuple[int, str]:
    score = 0
    reasons: list[str] = []

    event_amount = abs(_money(event.get("gross_amount")))
    reservation_amounts = [
        abs(_money(reservation.get("total_paid"))),
        abs(_money(reservation.get("total_payout"))),
        abs(
            _money(reservation.get("accommodation_revenue"))
            + _money(reservation.get("state_tax"))
            + _money(reservation.get("county_tax"))
            + _money(reservation.get("local_tax"))
        ),
    ]

    closest_amount = min(
        (
            abs(event_amount - amount)
            for amount in reservation_amounts
            if amount > 0
        ),
        default=999999.0,
    )

    if closest_amount <= 0.02:
        score += 45
        reasons.append("exact amount")
    elif closest_amount <= 5.00:
        score += 30
        reasons.append(f"amount within {closest_amount:.2f}")
    elif closest_amount <= 25.00:
        score += 15
        reasons.append(f"amount within {closest_amount:.2f}")

    confirmation_distance = _date_distance(
        event.get("transaction_date"),
        reservation.get("confirmation_date"),
    )
    check_in_distance = _date_distance(
        event.get("transaction_date"),
        reservation.get("check_in"),
    )

    best_date = min(
        [
            value
            for value in [
                confirmation_distance,
                check_in_distance,
            ]
            if value is not None
        ],
        default=None,
    )

    if best_date is not None:
        if best_date <= 2:
            score += 25
            reasons.append(f"date within {best_date} days")
        elif best_date <= 10:
            score += 15
            reasons.append(f"date within {best_date} days")
        elif best_date <= 30:
            score += 5
            reasons.append(f"date within {best_date} days")

    guest_similarity = _similarity(
        event.get("guest"),
        reservation.get("guest"),
    )
    if guest_similarity >= 0.90:
        score += 25
        reasons.append("strong guest-name match")
    elif guest_similarity >= 0.70:
        score += 15
        reasons.append("possible guest-name match")

    listing_similarity = _similarity(
        event.get("listing"),
        reservation.get("listing"),
    )
    if listing_similarity >= 0.85:
        score += 10
        reasons.append("listing match")
    elif listing_similarity >= 0.60:
        score += 5
        reasons.append("possible listing match")

    return min(score, 100), "; ".join(reasons)


def build_unlinked_stripe_review(
    *,
    payment_ledger: pd.DataFrame,
    reservations: pd.DataFrame,
    cognito_renewals: pd.DataFrame | None = None,
    top_n: int = 5,
) -> pd.DataFrame:
    reservation_ids = {
        _text(value)
        for value in reservations["reservation_id"]
        if _text(value)
    }
    channel_ids = {
        _text(value)
        for value in reservations["channel_reservation_id"]
        if _text(value)
    }

    stripe = payment_ledger.loc[
        payment_ledger["processor"]
        .astype(str)
        .str.strip()
        .eq("Stripe")
        & payment_ledger["payout_assignment_status"]
        .astype(str)
        .str.strip()
        .eq("Assigned")
    ].copy()

    def is_linked(row: pd.Series) -> bool:
        reservation_id = _text(row.get("reservation_id"))
        channel_id = _text(row.get("channel_reservation_id"))

        return (
            bool(reservation_id)
            and reservation_id in reservation_ids
        ) or (
            bool(channel_id)
            and channel_id in channel_ids
        )

    linked_mask = stripe.apply(is_linked, axis=1)
    unlinked = stripe.loc[~linked_mask].copy()

    rows: list[dict[str, Any]] = []

    for _, event in unlinked.iterrows():
        candidates: list[tuple[int, str, str, str]] = []

        for _, reservation in reservations.iterrows():
            score, reason = _candidate_score(
                event,
                reservation,
            )
            if score <= 0:
                continue

            candidates.append(
                (
                    score,
                    _text(reservation.get("reservation_id")),
                    _text(
                        reservation.get(
                            "channel_reservation_id"
                        )
                    ),
                    reason,
                )
            )

        candidates.sort(
            key=lambda item: (-item[0], item[1], item[2])
        )
        selected = candidates[:top_n]

        row: dict[str, Any] = {
            "payment_event_id": _text(
                event.get("payment_event_id")
            ),
            "payout_id": _text(event.get("payout_id")),
            "processor_account": _text(
                event.get("processor_account")
            ),
            "transaction_id": _text(
                event.get("transaction_id")
            ),
            "transaction_date": event.get(
                "transaction_date"
            ),
            "gross_amount": _money(
                event.get("gross_amount")
            ),
            "net_amount": _money(event.get("net_amount")),
            "guest_metadata": _text(event.get("guest")),
            "listing_metadata": _text(
                event.get("listing")
            ),
            "reservation_id_metadata": _text(
                event.get("reservation_id")
            ),
            "channel_id_metadata": _text(
                event.get("channel_reservation_id")
            ),
            "candidate_count": len(candidates),
            "recommended_action": (
                "Review top candidate"
                if selected
                else "Research source transaction"
            ),
        }

        for rank in range(1, top_n + 1):
            if rank <= len(selected):
                score, reservation_id, channel_id, reason = (
                    selected[rank - 1]
                )
            else:
                score, reservation_id, channel_id, reason = (
                    "",
                    "",
                    "",
                    "",
                )

            row[f"candidate_{rank}_score"] = score
            row[f"candidate_{rank}_reservation_id"] = (
                reservation_id
            )
            row[f"candidate_{rank}_channel_id"] = channel_id
            row[f"candidate_{rank}_reason"] = reason

        rows.append(row)

    columns = [
        "payment_event_id",
        "payout_id",
        "processor_account",
        "transaction_id",
        "transaction_date",
        "gross_amount",
        "net_amount",
        "guest_metadata",
        "listing_metadata",
        "reservation_id_metadata",
        "channel_id_metadata",
        "candidate_count",
        "recommended_action",
    ]

    for rank in range(1, top_n + 1):
        columns.extend(
            [
                f"candidate_{rank}_score",
                f"candidate_{rank}_reservation_id",
                f"candidate_{rank}_channel_id",
                f"candidate_{rank}_reason",
            ]
        )

    return pd.DataFrame(rows, columns=columns)
