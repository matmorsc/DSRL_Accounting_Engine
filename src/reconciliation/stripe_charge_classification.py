from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


LEDGER_COLUMNS = [
    "processor_account",
    "source_id",
    "charge_transaction_id",
    "reservation_id",
    "channel_reservation_id",
    "guest",
    "listing",
    "property_class",
    "income_account",
    "qb_class",
    "revenue_share",
    "state_tax_share",
    "county_tax_share",
    "local_tax_share",
    "classification_status",
    "classification_source",
    "notes",
]


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


def _share(value: object) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def read_charge_classification_ledger(
    path: Path,
) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=LEDGER_COLUMNS)

    frame = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
    )

    missing = [
        column
        for column in LEDGER_COLUMNS
        if column not in frame.columns
    ]
    if missing:
        raise ValueError(
            f"{path.name} missing columns: {missing}"
        )

    return frame[LEDGER_COLUMNS].copy()


def _reservation_indexes(
    reservations: pd.DataFrame,
) -> tuple[dict[str, pd.Series], dict[str, pd.Series]]:
    by_reservation = {
        _text(row.get("reservation_id")): row
        for _, row in reservations.iterrows()
        if _text(row.get("reservation_id"))
    }
    by_channel = {
        _text(row.get("channel_reservation_id")): row
        for _, row in reservations.iterrows()
        if _text(row.get("channel_reservation_id"))
    }
    return by_reservation, by_channel


def _lookup_reservation(
    charge: pd.Series,
    by_reservation: dict[str, pd.Series],
    by_channel: dict[str, pd.Series],
) -> pd.Series | None:
    reservation_id = _text(charge.get("reservation_id"))
    channel_id = _text(
        charge.get("channel_reservation_id")
    )

    if reservation_id and reservation_id in by_reservation:
        return by_reservation[reservation_id]

    if channel_id and channel_id in by_channel:
        return by_channel[channel_id]

    return None


def _classification_from_reservation(
    charge: pd.Series,
    reservation: pd.Series,
    classes: dict[str, str],
) -> dict[str, object]:
    components = {
        "revenue": _money(
            reservation.get("accommodation_revenue")
        ),
        "state_tax": _money(
            reservation.get("state_tax")
        ),
        "county_tax": _money(
            reservation.get("county_tax")
        ),
        "local_tax": _money(
            reservation.get("local_tax")
        ),
    }

    total = round(sum(components.values()), 2)

    if total <= 0:
        return {}

    return {
        "processor_account": _text(
            charge.get("processor_account")
        ),
        "source_id": _text(charge.get("source_id")),
        "charge_transaction_id": _text(
            charge.get("transaction_id")
        ),
        "reservation_id": _text(
            reservation.get("reservation_id")
        ),
        "channel_reservation_id": _text(
            reservation.get("channel_reservation_id")
        ),
        "guest": _text(reservation.get("guest")),
        "listing": _text(reservation.get("listing")),
        "property_class": _text(
            reservation.get("property_class")
        ),
        "income_account": _text(
            reservation.get("income_account")
        ),
        "qb_class": _text(
            classes.get(
                _text(reservation.get("property_class"))
            )
        ),
        "revenue_share": components["revenue"] / total,
        "state_tax_share": components["state_tax"] / total,
        "county_tax_share": components["county_tax"] / total,
        "local_tax_share": components["local_tax"] / total,
        "classification_status": "Active",
        "classification_source": "Guesty reservation",
        "notes": "",
    }


def build_charge_classification_ledger(
    *,
    payment_ledger: pd.DataFrame,
    reservations: pd.DataFrame,
    existing_ledger: pd.DataFrame,
    rules: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    classes = rules.get("classes", {})

    by_reservation, by_channel = _reservation_indexes(
        reservations
    )

    existing_lookup = {
        (
            _text(row.get("processor_account")),
            _text(row.get("source_id")),
        ): row
        for _, row in existing_ledger.iterrows()
        if _text(row.get("source_id"))
        and _text(row.get("classification_status")).lower()
        in {"active", "accepted"}
    }

    output_rows: list[dict[str, object]] = []
    diagnostic_rows: list[dict[str, object]] = []

    charges = payment_ledger.loc[
        payment_ledger["processor"]
        .astype(str)
        .str.strip()
        .eq("Stripe")
        & payment_ledger["transaction_type"]
        .astype(str)
        .str.lower()
        .str.strip()
        .eq("charge")
    ].copy()

    for _, charge in charges.iterrows():
        key = (
            _text(charge.get("processor_account")),
            _text(charge.get("source_id")),
        )

        existing = existing_lookup.get(key)
        if existing is not None:
            output_rows.append(
                {
                    column: existing.get(column, "")
                    for column in LEDGER_COLUMNS
                }
            )
            continue

        reservation = _lookup_reservation(
            charge,
            by_reservation,
            by_channel,
        )

        if reservation is None:
            diagnostic_rows.append(
                {
                    "processor_account": key[0],
                    "source_id": key[1],
                    "charge_transaction_id": _text(
                        charge.get("transaction_id")
                    ),
                    "diagnostic_type": (
                        "Unclassified Historical Charge"
                    ),
                    "detail": (
                        "Original Stripe charge could not be linked "
                        "to a current reservation."
                    ),
                    "reservation_id": _text(
                        charge.get("reservation_id")
                    ),
                    "channel_reservation_id": _text(
                        charge.get(
                            "channel_reservation_id"
                        )
                    ),
                    "guest": _text(charge.get("guest")),
                    "listing": _text(
                        charge.get("listing")
                    ),
                    "gross_amount": _money(
                        charge.get("gross_amount")
                    ),
                }
            )
            continue

        classification = (
            _classification_from_reservation(
                charge,
                reservation,
                classes,
            )
        )

        if not classification:
            diagnostic_rows.append(
                {
                    "processor_account": key[0],
                    "source_id": key[1],
                    "charge_transaction_id": _text(
                        charge.get("transaction_id")
                    ),
                    "diagnostic_type": (
                        "Invalid Classification Basis"
                    ),
                    "detail": (
                        "Reservation had no positive revenue/tax basis."
                    ),
                    "reservation_id": _text(
                        reservation.get("reservation_id")
                    ),
                    "channel_reservation_id": _text(
                        reservation.get(
                            "channel_reservation_id"
                        )
                    ),
                    "guest": _text(
                        reservation.get("guest")
                    ),
                    "listing": _text(
                        reservation.get("listing")
                    ),
                    "gross_amount": _money(
                        charge.get("gross_amount")
                    ),
                }
            )
            continue

        output_rows.append(classification)

    combined = pd.concat(
        [
            existing_ledger[LEDGER_COLUMNS].copy(),
            pd.DataFrame(
                output_rows,
                columns=LEDGER_COLUMNS,
            ),
        ],
        ignore_index=True,
    )

    if combined.empty:
        combined = pd.DataFrame(columns=LEDGER_COLUMNS)
    else:
        combined = combined.drop_duplicates(
            subset=[
                "processor_account",
                "source_id",
            ],
            keep="last",
        )

    share_columns = [
        "revenue_share",
        "state_tax_share",
        "county_tax_share",
        "local_tax_share",
    ]
    for column in share_columns:
        combined[column] = (
            pd.to_numeric(
                combined[column],
                errors="coerce",
            )
            .fillna(0.0)
        )

    return (
        combined[LEDGER_COLUMNS].sort_values(
            [
                "processor_account",
                "source_id",
            ]
        ).reset_index(drop=True),
        pd.DataFrame(diagnostic_rows),
    )


def write_charge_classification_ledger(
    frame: pd.DataFrame,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
