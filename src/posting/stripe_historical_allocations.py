from __future__ import annotations

from typing import Any

import pandas as pd


REFUND_LIKE_TYPES = {
    "refund",
    "adjustment",
    "reversal",
    "dispute",
}


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


def _classification_lookup(
    ledger: pd.DataFrame,
) -> dict[tuple[str, str], pd.Series]:
    return {
        (
            _text(row.get("processor_account")),
            _text(row.get("source_id")),
        ): row
        for _, row in ledger.iterrows()
        if _text(row.get("source_id"))
        and _text(row.get("classification_status")).lower()
        in {"active", "accepted"}
    }


def build_stripe_historical_allocations(
    *,
    payment_ledger: pd.DataFrame,
    charge_classification_ledger: pd.DataFrame,
    already_allocated_event_ids: set[str],
    rules: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    lookup = _classification_lookup(
        charge_classification_ledger
    )
    accounts = rules.get("accounts", {})
    classes = rules.get("classes", {})
    tax_descriptions = rules.get(
        "tax_descriptions",
        {},
    )

    allocation_rows: list[dict[str, object]] = []
    diagnostic_rows: list[dict[str, object]] = []

    candidates = payment_ledger.loc[
        payment_ledger["processor"]
        .astype(str)
        .str.strip()
        .eq("Stripe")
        & payment_ledger["transaction_type"]
        .astype(str)
        .str.lower()
        .str.strip()
        .isin(REFUND_LIKE_TYPES)
        & ~payment_ledger["payment_event_id"]
        .astype(str)
        .isin(already_allocated_event_ids)
    ].copy()

    for _, event in candidates.iterrows():
        event_id = _text(
            event.get("payment_event_id")
        )
        key = (
            _text(event.get("processor_account")),
            _text(event.get("source_id")),
        )
        classification = lookup.get(key)

        if classification is None:
            diagnostic_rows.append(
                {
                    "payment_event_id": event_id,
                    "payout_id": _text(
                        event.get("payout_id")
                    ),
                    "processor": "Stripe",
                    "diagnostic_type": (
                        "Missing Charge Classification"
                    ),
                    "detail": (
                        "Refund-like event could not reuse an "
                        "original charge classification."
                    ),
                    "event_amount": _money(
                        event.get("gross_amount")
                    ),
                    "source_id": key[1],
                }
            )
            continue

        event_amount = _money(
            event.get("gross_amount")
        )

        components = [
            (
                "Revenue",
                _share(classification.get("revenue_share")),
                _text(
                    classification.get("income_account")
                ),
                _text(classification.get("listing")),
                _text(classification.get("qb_class")),
            ),
            (
                "State Tax",
                _share(
                    classification.get(
                        "state_tax_share"
                    )
                ),
                _text(accounts.get("tax_payable")),
                _text(
                    tax_descriptions.get(
                        "state_tax",
                        "State",
                    )
                ),
                _text(classes.get("tax")),
            ),
            (
                "County Tax",
                _share(
                    classification.get(
                        "county_tax_share"
                    )
                ),
                _text(accounts.get("tax_payable")),
                _text(
                    tax_descriptions.get(
                        "county_tax",
                        "County",
                    )
                ),
                _text(classes.get("tax")),
            ),
            (
                "Local Tax",
                _share(
                    classification.get(
                        "local_tax_share"
                    )
                ),
                _text(accounts.get("tax_payable")),
                _text(
                    tax_descriptions.get(
                        "local_tax",
                        "Local",
                    )
                ),
                _text(classes.get("tax")),
            ),
        ]

        component_amounts = [
            round(event_amount * share, 2)
            for _, share, _, _, _ in components
        ]

        if component_amounts:
            residual = round(
                event_amount - sum(component_amounts),
                2,
            )
            component_amounts[0] = round(
                component_amounts[0] + residual,
                2,
            )

        for (
            component,
            _share_value,
            account,
            description,
            qb_class,
        ), amount in zip(
            components,
            component_amounts,
        ):
            if abs(amount) < 0.005:
                continue

            allocation_rows.append(
                {
                    "payment_event_id": event_id,
                    "payout_id": _text(
                        event.get("payout_id")
                    ),
                    "processor": "Stripe",
                    "processor_account": key[0],
                    "transaction_id": _text(
                        event.get("transaction_id")
                    ),
                    "transaction_type": _text(
                        event.get("transaction_type")
                    ),
                    "transaction_date": event.get(
                        "transaction_date"
                    ),
                    "reservation_id": _text(
                        classification.get(
                            "reservation_id"
                        )
                    ),
                    "channel_reservation_id": _text(
                        classification.get(
                            "channel_reservation_id"
                        )
                    ),
                    "guest": _text(
                        classification.get("guest")
                    ),
                    "listing": _text(
                        classification.get("listing")
                    ),
                    "property_class": _text(
                        classification.get(
                            "property_class"
                        )
                    ),
                    "match_method": (
                        "Stripe charge classification ledger"
                    ),
                    "allocation_type": component,
                    "account": account,
                    "description": description,
                    "amount": amount,
                    "class": qb_class,
                }
            )

    columns = [
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

    return (
        pd.DataFrame(
            allocation_rows,
            columns=columns,
        ),
        pd.DataFrame(diagnostic_rows),
    )


def _share(value: object) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0
