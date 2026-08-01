from __future__ import annotations

from pathlib import Path

import pandas as pd


VALID_OVERRIDE_TYPES = {
    "Approved Refund",
    "Reservation Modification",
    "Cash Received - Awaiting Deposit",
    "Booking.com Collection Issue",
    "Expected Future Manual Payment",
    "Expected Future Airbnb Payment",
    "Outside Reporting Scope",
    "Cancelled Reservation",
    "Accepted Difference",
}

REQUIRED_OVERRIDE_COLUMNS = {
    "reservation_id",
    "channel_reservation_id",
    "override_type",
    "effective_date",
    "amount",
    "notes",
    "status",
}


def _norm(value: object) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if text.lower() == "nan":
        return ""

    return text


def _read_overrides(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=sorted(REQUIRED_OVERRIDE_COLUMNS))

    frame = pd.read_csv(path, dtype=str, keep_default_na=False)

    missing = sorted(REQUIRED_OVERRIDE_COLUMNS.difference(frame.columns))
    if missing:
        raise ValueError(
            f"Manual overrides missing columns: {missing}"
        )

    frame = frame.copy()
    frame["override_type"] = (
        frame["override_type"].astype(str).str.strip()
    )
    frame["status"] = frame["status"].astype(str).str.strip()

    invalid = sorted(
        set(frame.loc[
            frame["override_type"].ne(""),
            "override_type",
        ]).difference(VALID_OVERRIDE_TYPES)
    )

    if invalid:
        raise ValueError(
            "Invalid override types: " + ", ".join(invalid)
        )

    active = frame.loc[
        ~frame["status"].str.lower().isin(
            {"inactive", "superseded", "void"}
        )
    ].copy()

    return active


def _select_override(
    reservation: pd.Series,
    overrides: pd.DataFrame,
) -> pd.Series | None:
    reservation_id = _norm(
        reservation.get("reservation_id")
    )
    channel_id = _norm(
        reservation.get("channel_reservation_id")
    )

    candidates = overrides.loc[
        (
            overrides["reservation_id"]
            .astype(str)
            .str.strip()
            .eq(reservation_id)
            & (reservation_id != "")
        )
        |
        (
            overrides["channel_reservation_id"]
            .astype(str)
            .str.strip()
            .eq(channel_id)
            & (channel_id != "")
        )
    ]

    if candidates.empty:
        return None

    if len(candidates) > 1:
        raise ValueError(
            "Multiple active overrides found for reservation "
            f"{reservation_id or channel_id}"
        )

    return candidates.iloc[0]


def _processor_totals(
    reservation: pd.Series,
    processor_transactions: pd.DataFrame,
) -> tuple[float, float]:
    reservation_id = _norm(
        reservation.get("reservation_id")
    )
    channel_id = _norm(
        reservation.get("channel_reservation_id")
    )

    linked = processor_transactions.loc[
        (
            processor_transactions["reservation_id"]
            .astype(str)
            .str.strip()
            .eq(reservation_id)
            & (reservation_id != "")
        )
        |
        (
            processor_transactions["channel_reservation_id"]
            .astype(str)
            .str.strip()
            .eq(channel_id)
            & (channel_id != "")
        )
    ].copy()

    payments = linked.loc[
        linked["transaction_type"].isin(
            {"charge", "payment", "reservation"}
        )
    ]

    refunds = linked.loc[
        linked["transaction_type"].eq("refund")
    ]

    payment_total = round(
        payments["gross_amount"].abs().sum(),
        2,
    )

    refund_total = round(
        refunds["gross_amount"].abs().sum(),
        2,
    )

    return payment_total, refund_total


def _automatic_status(
    reservation: pd.Series,
    match: pd.Series,
    acquisition_date: pd.Timestamp,
    today: pd.Timestamp,
    processor_payment_total: float,
    processor_refund_total: float,
    amount_tolerance: float,
) -> tuple[str, str, str]:
    source = _norm(reservation.get("source")).lower()
    payment_method = _norm(
        reservation.get("payment_method")
    ).lower()

    confirmation_date = pd.to_datetime(
        reservation.get("confirmation_date"),
        errors="coerce",
    )
    check_in = pd.to_datetime(
        reservation.get("check_in"),
        errors="coerce",
    )
    check_out = pd.to_datetime(
        reservation.get("check_out"),
        errors="coerce",
    )

    total_paid = float(
        reservation.get("total_paid", 0.0)
    )
    total_refunded = float(
        reservation.get("total_refunded", 0.0)
    )
    balance_due = float(
        reservation.get("balance_due", 0.0)
    )

    match_status = _norm(
        match.get("match_status")
    )

    if (
        pd.notna(check_out)
        and check_out < acquisition_date
    ):
        return (
            "Outside Reporting Scope",
            "Expected / informational",
            "Reservation ended before acquisition date.",
        )

    if (
        source.startswith("airbnb")
        and pd.notna(check_out)
        and check_out.normalize() >= today.normalize()
        and processor_payment_total <= amount_tolerance
    ):
        return (
            "Expected Future Airbnb Payment",
            "Expected / informational",
            "Airbnb normally pays after checkout.",
        )

    if (
        payment_method in {"cash", "check", "cash / check"}
        and pd.notna(check_in)
        and check_in.normalize() >= today.normalize()
        and total_paid <= amount_tolerance
    ):
        return (
            "Expected Future Manual Payment",
            "Expected / informational",
            "Manual payment is expected at or near check-in.",
        )

    if (
        source.startswith("booking")
        and match_status == "No Processor Match"
        and (
            pd.isna(check_in)
            or check_in.normalize() <= today.normalize()
        )
    ):
        return (
            "Booking.com Collection Issue",
            "Needs operational follow-up",
            "Booking.com reservation has no processor match.",
        )

    if balance_due > amount_tolerance:
        return (
            "Balance Due",
            "Needs operational follow-up",
            "Guesty reports an unpaid balance.",
        )

    if payment_method in {"cash", "check", "cash / check"}:
        return (
            "Cash / Manual Review",
            "Needs human review",
            "Confirm collection and deposit status.",
        )

    if match_status in {
        "Single Legacy Candidate",
        "Multiple Legacy Candidates",
    }:
        return (
            match_status,
            "Needs human review",
            "Legacy Stripe candidate must be manually approved.",
        )

    if match_status == "No Processor Match":
        return (
            "No Payment Source Found",
            "Needs accounting follow-up",
            "No processor payment or legacy candidate was found.",
        )

    payment_difference = round(
        processor_payment_total - total_paid,
        2,
    )
    refund_difference = round(
        processor_refund_total - total_refunded,
        2,
    )

    if abs(refund_difference) > amount_tolerance:
        return (
            "Refund Discrepancy",
            "Needs accounting follow-up",
            (
                "Guesty and processor refund totals differ by "
                f"{refund_difference:.2f}."
            ),
        )

    if abs(payment_difference) > amount_tolerance:
        return (
            "Payment Amount Mismatch",
            "Needs accounting follow-up",
            (
                "Guesty and processor payment totals differ by "
                f"{payment_difference:.2f}."
            ),
        )

    if match_status == "Exact Match":
        return (
            "Processor Matched",
            "Ready for payout reconciliation",
            "Reservation and processor transaction are linked.",
        )

    return (
        "Needs Review",
        "Needs human review",
        "No reconciliation rule produced a final status.",
    )


def _override_status(
    override: pd.Series,
) -> tuple[str, str, str]:
    override_type = _norm(
        override.get("override_type")
    )
    notes = _norm(override.get("notes"))

    categories = {
        "Approved Refund": "Documented business event",
        "Reservation Modification": "Documented business event",
        "Cash Received - Awaiting Deposit": "Needs operational follow-up",
        "Booking.com Collection Issue": "Needs operational follow-up",
        "Expected Future Manual Payment": "Expected / informational",
        "Expected Future Airbnb Payment": "Expected / informational",
        "Outside Reporting Scope": "Expected / informational",
        "Cancelled Reservation": "Documented business event",
        "Accepted Difference": "Documented business event",
    }

    return (
        override_type,
        categories.get(
            override_type,
            "Needs human review",
        ),
        notes or "Manual override applied.",
    )


def build_reconciliation(
    reservations: pd.DataFrame,
    matches: pd.DataFrame,
    processor_transactions: pd.DataFrame,
    overrides_path: Path,
    acquisition_date: str,
    amount_tolerance: float = 0.02,
    as_of_date: str | None = None,
) -> pd.DataFrame:
    required_reservation_columns = {
        "reservation_id",
        "channel_reservation_id",
        "guest",
        "listing",
        "property_class",
        "source",
        "payment_method",
        "confirmation_date",
        "check_in",
        "check_out",
        "income_account",
        "total_paid",
        "total_refunded",
        "balance_due",
    }

    missing = sorted(
        required_reservation_columns.difference(
            reservations.columns
        )
    )

    if missing:
        raise ValueError(
            f"Reservations missing columns: {missing}"
        )

    if len(reservations) != len(matches):
        raise ValueError(
            "Reservation and match row counts do not agree."
        )

    overrides = _read_overrides(overrides_path)

    acquisition = pd.to_datetime(
        acquisition_date,
        errors="raise",
    )

    today = (
        pd.to_datetime(as_of_date, errors="raise")
        if as_of_date
        else pd.Timestamp.today()
    )

    rows: list[dict[str, object]] = []

    for index, reservation in reservations.iterrows():
        match = matches.iloc[index]

        override = _select_override(
            reservation,
            overrides,
        )

        processor_payment_total, processor_refund_total = (
            _processor_totals(
                reservation,
                processor_transactions,
            )
        )

        if override is not None:
            status, category, explanation = _override_status(
                override
            )
            override_type = _norm(
                override.get("override_type")
            )
            override_notes = _norm(
                override.get("notes")
            )
            override_amount = pd.to_numeric(
                override.get("amount"),
                errors="coerce",
            )
        else:
            status, category, explanation = _automatic_status(
                reservation=reservation,
                match=match,
                acquisition_date=acquisition,
                today=today,
                processor_payment_total=processor_payment_total,
                processor_refund_total=processor_refund_total,
                amount_tolerance=amount_tolerance,
            )
            override_type = ""
            override_notes = ""
            override_amount = float("nan")

        review_required = (
            "No"
            if category in {
                "Expected / informational",
                "Documented business event",
                "Ready for payout reconciliation",
            }
            else "Yes"
        )

        rows.append(
            {
                "reconciliation_id": _norm(
                    match.get("reconciliation_id")
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
                "property_class": _norm(
                    reservation.get("property_class")
                ),
                "income_account": _norm(
                    reservation.get("income_account")
                ),
                "source": _norm(
                    reservation.get("source")
                ),
                "payment_method": _norm(
                    reservation.get("payment_method")
                ),
                "confirmation_date": reservation.get(
                    "confirmation_date"
                ),
                "check_in": reservation.get("check_in"),
                "check_out": reservation.get("check_out"),
                "guesty_total_paid": float(
                    reservation.get("total_paid", 0.0)
                ),
                "guesty_total_refunded": float(
                    reservation.get("total_refunded", 0.0)
                ),
                "guesty_balance_due": float(
                    reservation.get("balance_due", 0.0)
                ),
                "processor_payment_total": (
                    processor_payment_total
                ),
                "processor_refund_total": (
                    processor_refund_total
                ),
                "payment_difference": round(
                    processor_payment_total
                    - float(
                        reservation.get("total_paid", 0.0)
                    ),
                    2,
                ),
                "refund_difference": round(
                    processor_refund_total
                    - float(
                        reservation.get(
                            "total_refunded",
                            0.0,
                        )
                    ),
                    2,
                ),
                "match_status": _norm(
                    match.get("match_status")
                ),
                "match_method": _norm(
                    match.get("match_method")
                ),
                "confidence_score": int(
                    match.get("confidence_score", 0)
                ),
                "override_type": override_type,
                "override_amount": override_amount,
                "override_notes": override_notes,
                "reconciliation_status": status,
                "status_category": category,
                "status_explanation": explanation,
                "review_required": review_required,
                "as_of_date": today.normalize(),
            }
        )

    return pd.DataFrame(rows)
