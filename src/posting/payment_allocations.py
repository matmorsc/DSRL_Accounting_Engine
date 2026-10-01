from __future__ import annotations

from typing import Any

import pandas as pd

from src.review.original_charge_reconstruction import (
    reconstruct_tax_allocation,
)


REQUIRED_PAYMENT_COLUMNS = {
    "payment_event_id",
    "processor",
    "processor_account",
    "transaction_id",
    "transaction_type",
    "transaction_date",
    "gross_amount",
    "processor_fee",
    "net_amount",
    "reservation_id",
    "channel_reservation_id",
    "payout_id",
    "payout_assignment_status",
}

REQUIRED_RESERVATION_COLUMNS = {
    "reservation_id",
    "channel_reservation_id",
    "guest",
    "listing",
    "property_class",
    "income_account",
    "accommodation_revenue",
    "state_tax",
    "county_tax",
    "local_tax",
    "total_paid",
    "total_refunded",
}


def _require(
    frame: pd.DataFrame,
    required: set[str],
    label: str,
) -> None:
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


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


def _parsed_money(value: object) -> tuple[float, bool]:
    try:
        if pd.isna(value):
            return 0.0, False
        return round(float(value), 2), True
    except (TypeError, ValueError):
        return 0.0, False


def _parsed_rate(value: object) -> tuple[float, bool]:
    try:
        if pd.isna(value):
            return 0.0, False
        return float(value), True
    except (TypeError, ValueError):
        return 0.0, False


def _active_original_event_ids(
    existing_history: pd.DataFrame | None,
) -> set[str]:
    if existing_history is None or existing_history.empty:
        return set()
    required = {"payment_event_id", "posting_type", "status"}
    if not required.issubset(existing_history.columns):
        return set()

    return set(
        existing_history.loc[
            existing_history["posting_type"]
            .astype(str)
            .str.strip()
            .eq("Original")
            & existing_history["status"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("active"),
            "payment_event_id",
        ]
        .astype(str)
        .str.strip()
    )


def _signed_event_amount(
    transaction_type: str,
    gross_amount: float,
) -> float:
    event_type = transaction_type.lower().strip()
    amount = abs(gross_amount)

    if event_type in {"refund", "reversal", "dispute"}:
        return -amount

    if event_type in {
        "adjustment",
        "resolution adjustment",
        "cancellation fee",
    }:
        # Airbnb exports already provide the accounting sign for these
        # source events. A negative adjustment must remain negative.
        return round(gross_amount, 2)

    return amount


def _reservation_indexes(
    reservations: pd.DataFrame,
) -> tuple[dict[str, pd.Series], dict[str, pd.Series]]:
    by_reservation = {
        _text(row["reservation_id"]): row
        for _, row in reservations.iterrows()
        if _text(row["reservation_id"])
    }
    by_channel = {
        _text(row["channel_reservation_id"]): row
        for _, row in reservations.iterrows()
        if _text(row["channel_reservation_id"])
    }
    return by_reservation, by_channel


def _lookup_reservation(
    event: pd.Series,
    by_reservation: dict[str, pd.Series],
    by_channel: dict[str, pd.Series],
) -> tuple[pd.Series | None, str]:
    reservation_id = _text(event.get("reservation_id"))
    channel_id = _text(event.get("channel_reservation_id"))

    if reservation_id and reservation_id in by_reservation:
        return by_reservation[reservation_id], "Reservation ID"

    if channel_id and channel_id in by_channel:
        return by_channel[channel_id], "Channel Reservation ID"

    return None, ""


def _allocate_direct_event(
    *,
    event_amount: float,
    reservation: pd.Series,
) -> tuple[dict[str, float], str]:
    components = {
        "Revenue": _money(
            reservation.get("accommodation_revenue")
        ),
        "State Tax": _money(reservation.get("state_tax")),
        "County Tax": _money(reservation.get("county_tax")),
        "Local Tax": _money(reservation.get("local_tax")),
    }

    expected_total = round(sum(components.values()), 2)

    if expected_total <= 0:
        return {}, "Reservation has no positive revenue/tax allocation basis."

    ratio = event_amount / expected_total
    allocations = {
        name: round(amount * ratio, 2)
        for name, amount in components.items()
    }

    # Force exact equality after rounding. Revenue receives the penny residual.
    residual = round(event_amount - sum(allocations.values()), 2)
    allocations["Revenue"] = round(
        allocations["Revenue"] + residual,
        2,
    )

    note = ""
    if abs(ratio) > 1.0001:
        note = (
            f"Event amount exceeds reservation revenue/tax basis "
            f"(ratio {ratio:.4f})."
        )

    return allocations, note


def _allocate_marketplace_event(
    *,
    event_amount: float,
) -> dict[str, float]:
    # Marketplace-remitted tax is not part of DSRL's deposit split.
    return {"Revenue": round(event_amount, 2)}


def _attempt_zero_basis_reconstruction(
    *,
    event: pd.Series,
    reservation: pd.Series,
    rules: dict[str, Any],
    income_account: str,
    qb_class: str,
    active_original_event_ids: set[str],
) -> tuple[dict[str, float], str, str]:
    reasons: list[str] = []
    settings = rules.get(
        "zero_basis_reconstruction",
        {},
    )

    event_id = _text(event.get("payment_event_id"))
    processor = _text(event.get("processor"))
    event_type = _text(event.get("transaction_type")).lower()
    listing = _text(reservation.get("listing"))

    enabled_processors = {
        _text(value)
        for value in settings.get(
            "enabled_processors",
            ["Stripe"],
        )
    }
    enabled_types = {
        _text(value).lower()
        for value in settings.get(
            "transaction_types",
            ["charge"],
        )
    }

    tolerance = float(
        rules.get("amount_tolerance", 0.02)
    )
    gross, gross_valid = _parsed_money(
        event.get("gross_amount")
    )
    fee, fee_valid = _parsed_money(
        event.get("processor_fee")
    )
    net, net_valid = _parsed_money(
        event.get("net_amount")
    )

    component_total = round(
        _money(reservation.get("accommodation_revenue"))
        + _money(reservation.get("state_tax"))
        + _money(reservation.get("county_tax"))
        + _money(reservation.get("local_tax")),
        2,
    )

    if processor not in enabled_processors:
        reasons.append(
            f"Processor {processor} is not enabled for zero-basis reconstruction."
        )
    if event_type not in enabled_types:
        reasons.append(
            f"Transaction type {event_type} is not enabled for zero-basis reconstruction."
        )
    if not gross_valid or gross <= 0:
        reasons.append(
            "Gross amount is missing, invalid, or non-positive."
        )
    if not fee_valid or fee < 0:
        reasons.append(
            "Processor fee is missing or invalid for reconstruction."
        )
    if not net_valid:
        reasons.append(
            "Net amount is missing or invalid for reconstruction."
        )
    if not listing:
        reasons.append(
            "Listing metadata is missing."
        )
    if not income_account:
        reasons.append(
            "Listing does not map to a revenue account."
        )
    if not qb_class:
        reasons.append(
            "Listing does not map to a QuickBooks class."
        )
    if component_total > 0.005:
        reasons.append(
            "Reservation already has positive revenue/tax basis."
        )
    if event_id in active_original_event_ids:
        reasons.append(
            "Event already has active Original posting history."
        )

    state_rate, state_ok = _parsed_rate(
        settings.get("state_rate")
    )
    local_rate, local_ok = _parsed_rate(
        settings.get("local_rate")
    )
    if not state_ok or state_rate <= 0:
        reasons.append(
            "Missing or invalid zero-basis state tax rate configuration."
        )
    if not local_ok or local_rate <= 0:
        reasons.append(
            "Missing or invalid zero-basis local tax rate configuration."
        )

    if reasons:
        return {}, "", " ".join(reasons)

    try:
        revenue, state_tax, local_tax = (
            reconstruct_tax_allocation(
                gross_amount=gross,
                state_rate=state_rate,
                local_rate=local_rate,
            )
        )
    except ValueError as exc:
        return {}, "", str(exc)

    gross_total = round(
        revenue + state_tax + local_tax,
        2,
    )
    reconstructed_net = round(
        gross_total - abs(fee),
        2,
    )

    if abs(gross_total - gross) > tolerance:
        return (
            {},
            "",
            (
                "Reconstruction failed gross reconciliation: "
                f"{gross_total:.2f} vs {gross:.2f}."
            ),
        )

    if abs(reconstructed_net - net) > tolerance:
        return (
            {},
            "",
            (
                "Reconstruction failed net reconciliation: "
                f"{reconstructed_net:.2f} vs {net:.2f}."
            ),
        )

    detail = (
        "Stripe zero-basis reservation allocation reconstructed "
        "from processor gross using configured tax rates."
    )
    return (
        {
            "Revenue": revenue,
            "State Tax": state_tax,
            "Local Tax": local_tax,
        },
        detail,
        "",
    )


def build_payment_allocations(
    *,
    payment_ledger: pd.DataFrame,
    reservations: pd.DataFrame,
    rules: dict[str, Any],
    existing_history: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    _require(
        payment_ledger,
        REQUIRED_PAYMENT_COLUMNS,
        "Payment ledger",
    )
    _require(
        reservations,
        REQUIRED_RESERVATION_COLUMNS,
        "Reservations",
    )

    marketplace_processors = set(
        rules.get(
            "marketplace_remitted_tax_processors",
            [],
        )
    )
    classes = rules.get("classes", {})
    accounts = rules.get("accounts", {})
    fee_accounts = rules.get(
        "processor_fee_accounts",
        {},
    )
    tax_descriptions = rules.get(
        "tax_descriptions",
        {},
    )

    by_reservation, by_channel = _reservation_indexes(
        reservations
    )
    active_original_event_ids = _active_original_event_ids(
        existing_history
    )

    allocation_rows: list[dict[str, object]] = []
    diagnostic_rows: list[dict[str, object]] = []

    assigned = payment_ledger.loc[
        payment_ledger["payout_assignment_status"]
        .astype(str)
        .str.strip()
        .eq("Assigned")
        & payment_ledger["payout_id"]
        .astype(str)
        .str.strip()
        .ne("")
    ].copy()

    for _, event in assigned.iterrows():
        event_id = _text(event.get("payment_event_id"))
        payout_id = _text(event.get("payout_id"))
        processor = _text(event.get("processor"))
        event_type = _text(event.get("transaction_type"))
        gross = _money(event.get("gross_amount"))
        fee = abs(_money(event.get("processor_fee")))
        signed_amount = _signed_event_amount(
            event_type,
            gross,
        )

        reservation, match_method = _lookup_reservation(
            event,
            by_reservation,
            by_channel,
        )

        if reservation is None:
            diagnostic_rows.append(
                {
                    "payment_event_id": event_id,
                    "payout_id": payout_id,
                    "processor": processor,
                    "diagnostic_type": "Unlinked Payment Event",
                    "detail": (
                        "Payment event could not be linked to a reservation."
                    ),
                    "event_amount": signed_amount,
                }
            )
            continue

        property_class = _text(
            reservation.get("property_class")
        )
        qb_class = _text(classes.get(property_class))
        income_account = _text(
            reservation.get("income_account")
        )

        if processor in marketplace_processors:
            allocations = _allocate_marketplace_event(
                event_amount=signed_amount
            )
            allocation_note = ""
        else:
            allocations, allocation_note = (
                _allocate_direct_event(
                    event_amount=signed_amount,
                    reservation=reservation,
                )
            )

            if not allocations:
                (
                    reconstructed,
                    reconstructed_note,
                    reconstructed_block_reason,
                ) = _attempt_zero_basis_reconstruction(
                    event=event,
                    reservation=reservation,
                    rules=rules,
                    income_account=income_account,
                    qb_class=qb_class,
                    active_original_event_ids=active_original_event_ids,
                )

                if reconstructed:
                    allocations = reconstructed
                    diagnostic_rows.append(
                        {
                            "payment_event_id": event_id,
                            "payout_id": payout_id,
                            "processor": processor,
                            "diagnostic_type": "Zero-Basis Reconstruction",
                            "detail": reconstructed_note,
                            "event_amount": signed_amount,
                        }
                    )
                    allocation_note = ""
                elif reconstructed_block_reason:
                    diagnostic_rows.append(
                        {
                            "payment_event_id": event_id,
                            "payout_id": payout_id,
                            "processor": processor,
                            "diagnostic_type": "Zero-Basis Reconstruction Skipped",
                            "detail": reconstructed_block_reason,
                            "event_amount": signed_amount,
                        }
                    )

        if allocation_note:
            diagnostic_rows.append(
                {
                    "payment_event_id": event_id,
                    "payout_id": payout_id,
                    "processor": processor,
                    "diagnostic_type": "Allocation Warning",
                    "detail": allocation_note,
                    "event_amount": signed_amount,
                }
            )

        component_mapping = {
            "Revenue": (
                income_account,
                _text(reservation.get("listing")),
                qb_class,
            ),
            "State Tax": (
                _text(accounts.get("tax_payable")),
                _text(
                    tax_descriptions.get(
                        "state_tax",
                        "State",
                    )
                ),
                _text(classes.get("tax")),
            ),
            "County Tax": (
                _text(accounts.get("tax_payable")),
                _text(
                    tax_descriptions.get(
                        "county_tax",
                        "County",
                    )
                ),
                _text(classes.get("tax")),
            ),
            "Local Tax": (
                _text(accounts.get("tax_payable")),
                _text(
                    tax_descriptions.get(
                        "local_tax",
                        "Local",
                    )
                ),
                _text(classes.get("tax")),
            ),
        }

        for component, amount in allocations.items():
            if abs(amount) < 0.005:
                continue

            account, description, component_class = (
                component_mapping[component]
            )

            allocation_rows.append(
                {
                    "payment_event_id": event_id,
                    "payout_id": payout_id,
                    "processor": processor,
                    "processor_account": _text(
                        event.get("processor_account")
                    ),
                    "transaction_id": _text(
                        event.get("transaction_id")
                    ),
                    "transaction_type": event_type,
                    "transaction_date": event.get(
                        "transaction_date"
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
                    "property_class": property_class,
                    "match_method": match_method,
                    "allocation_type": component,
                    "account": account,
                    "description": description,
                    "amount": round(amount, 2),
                    "class": component_class,
                }
            )

        if fee > 0:
            fee_account = _text(
                fee_accounts.get(processor)
            )

            if not fee_account:
                diagnostic_rows.append(
                    {
                        "payment_event_id": event_id,
                        "payout_id": payout_id,
                        "processor": processor,
                        "diagnostic_type": "Missing Fee Account",
                        "detail": (
                            f"No processor fee account configured for {processor}."
                        ),
                        "event_amount": signed_amount,
                    }
                )

            allocation_rows.append(
                {
                    "payment_event_id": event_id,
                    "payout_id": payout_id,
                    "processor": processor,
                    "processor_account": _text(
                        event.get("processor_account")
                    ),
                    "transaction_id": _text(
                        event.get("transaction_id")
                    ),
                    "transaction_type": event_type,
                    "transaction_date": event.get(
                        "transaction_date"
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
                    "property_class": property_class,
                    "match_method": match_method,
                    "allocation_type": "Processor Fee",
                    "account": fee_account,
                    "description": (
                        f"{processor} processing fees"
                    ),
                    "amount": round(-fee, 2),
                    "class": _text(classes.get("fees")),
                }
            )

    allocation_columns = [
        "payment_event_id",
        "payout_id",
        "processor",
        "processor_account",
        "transaction_id",
        "transaction_type",
        "transaction_date",
        "reservation_id",
        "channel_reservation_id",
        "guest",
        "listing",
        "property_class",
        "match_method",
        "allocation_type",
        "account",
        "description",
        "amount",
        "class",
    ]

    diagnostic_columns = [
        "payment_event_id",
        "payout_id",
        "processor",
        "diagnostic_type",
        "detail",
        "event_amount",
    ]

    return (
        pd.DataFrame(
            allocation_rows,
            columns=allocation_columns,
        ),
        pd.DataFrame(
            diagnostic_rows,
            columns=diagnostic_columns,
        ),
    )
