from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pandas as pd

from src.posting.history import POSTING_HISTORY_COLUMNS


REFUND_TYPES = {"refund", "reversal", "dispute"}
FEE_REFUND_TYPES = {"adjustment"}


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


def _stable_id(prefix: str, parts: list[str]) -> str:
    digest = sha256(
        "|".join(parts).encode("utf-8")
    ).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _active_originals(
    posting_history: pd.DataFrame,
) -> pd.DataFrame:
    return posting_history.loc[
        posting_history["status"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("active")
        & posting_history["posting_type"]
        .astype(str)
        .str.strip()
        .eq("Original")
    ].copy()


def _already_reversed_events(
    posting_history: pd.DataFrame,
) -> set[str]:
    return set(
        posting_history.loc[
            posting_history["posting_type"]
            .astype(str)
            .str.strip()
            .eq("Reversal"),
            "payment_event_id",
        ]
        .astype(str)
        .str.strip()
    )


def _select_basis(
    originals: pd.DataFrame,
    transaction_type: str,
) -> tuple[pd.DataFrame, str]:
    amounts = pd.to_numeric(
        originals["signed_amount"],
        errors="coerce",
    ).fillna(0.0)

    if transaction_type in REFUND_TYPES:
        basis = originals.loc[amounts.gt(0)].copy()
        return basis, "Positive original posting lines"

    if transaction_type in FEE_REFUND_TYPES:
        basis = originals.loc[amounts.lt(0)].copy()
        return basis, "Negative original posting lines"

    return pd.DataFrame(columns=originals.columns), ""


def _proportional_amounts(
    basis: pd.DataFrame,
    event_amount: float,
) -> list[float]:
    original = pd.to_numeric(
        basis["signed_amount"],
        errors="coerce",
    ).fillna(0.0)

    weights = original.abs()
    total = float(weights.sum())

    if total <= 0:
        return []

    allocated = [
        round(event_amount * float(weight) / total, 2)
        for weight in weights
    ]

    residual = round(
        event_amount - sum(allocated),
        2,
    )
    if allocated:
        allocated[0] = round(
            allocated[0] + residual,
            2,
        )

    return allocated


def build_reversal_preview(
    *,
    payment_ledger: pd.DataFrame,
    posting_history: pd.DataFrame,
    created_at: str,
    created_by: str = "DSRL Accounting Engine V8 Phase C",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    originals = _active_originals(posting_history)
    already_reversed = _already_reversed_events(
        posting_history
    )

    reversal_rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []

    source_events = payment_ledger.loc[
        payment_ledger["processor"]
        .astype(str)
        .str.strip()
        .eq("Stripe")
        & payment_ledger["transaction_type"]
        .astype(str)
        .str.lower()
        .str.strip()
        .isin(REFUND_TYPES | FEE_REFUND_TYPES)
    ].copy()

    for _, event in source_events.iterrows():
        event_id = _text(
            event.get("payment_event_id")
        )
        transaction_type = _text(
            event.get("transaction_type")
        ).lower()
        processor_account = _text(
            event.get("processor_account")
        )
        source_id = _text(event.get("source_id"))
        event_amount = _money(
            event.get("gross_amount")
        )

        if event_id in already_reversed:
            continue

        source_originals = originals.loc[
            originals["processor"]
            .astype(str)
            .str.strip()
            .eq("Stripe")
            & originals["processor_account"]
            .astype(str)
            .str.strip()
            .eq(processor_account)
            & originals["source_id"]
            .astype(str)
            .str.strip()
            .eq(source_id)
        ].copy()

        if source_originals.empty:
            review_rows.append(
                {
                    "payment_event_id": event_id,
                    "processor_account": processor_account,
                    "transaction_id": _text(
                        event.get("transaction_id")
                    ),
                    "transaction_type": transaction_type,
                    "transaction_date": event.get(
                        "transaction_date"
                    ),
                    "source_id": source_id,
                    "payout_id": _text(
                        event.get("payout_id")
                    ),
                    "event_amount": event_amount,
                    "reservation_id": _text(
                        event.get("reservation_id")
                    ),
                    "channel_reservation_id": _text(
                        event.get(
                            "channel_reservation_id"
                        )
                    ),
                    "guest": _text(event.get("guest")),
                    "listing": _text(
                        event.get("listing")
                    ),
                    "review_status": (
                        "Missing Original Posting History"
                    ),
                    "review_reason": (
                        "No active Original posting lines exist "
                        "for this Stripe Source."
                    ),
                    "required_action": (
                        "Create and approve the original charge "
                        "posting history before generating reversals."
                    ),
                }
            )
            continue

        basis, basis_description = _select_basis(
            source_originals,
            transaction_type,
        )

        if basis.empty:
            review_rows.append(
                {
                    "payment_event_id": event_id,
                    "processor_account": processor_account,
                    "transaction_id": _text(
                        event.get("transaction_id")
                    ),
                    "transaction_type": transaction_type,
                    "transaction_date": event.get(
                        "transaction_date"
                    ),
                    "source_id": source_id,
                    "payout_id": _text(
                        event.get("payout_id")
                    ),
                    "event_amount": event_amount,
                    "reservation_id": _text(
                        event.get("reservation_id")
                    ),
                    "channel_reservation_id": _text(
                        event.get(
                            "channel_reservation_id"
                        )
                    ),
                    "guest": _text(event.get("guest")),
                    "listing": _text(
                        event.get("listing")
                    ),
                    "review_status": (
                        "Missing Reversal Basis"
                    ),
                    "review_reason": (
                        "Original postings exist, but none match "
                        "the required sign basis."
                    ),
                    "required_action": (
                        "Review original posting lines and event type."
                    ),
                }
            )
            continue

        amounts = _proportional_amounts(
            basis,
            event_amount,
        )

        group_id = _stable_id(
            "rg",
            [
                event_id,
                processor_account,
                source_id,
                _text(event.get("payout_id")),
            ],
        )

        for (_, original), amount in zip(
            basis.iterrows(),
            amounts,
        ):
            original_line_id = _text(
                original.get("posting_line_id")
            )
            line_id = _stable_id(
                "rl",
                [
                    group_id,
                    original_line_id,
                    f"{amount:.2f}",
                ],
            )

            reversal_rows.append(
                {
                    "posting_line_id": line_id,
                    "posting_group_id": group_id,
                    "payment_event_id": event_id,
                    "processor": "Stripe",
                    "processor_account": processor_account,
                    "transaction_id": _text(
                        event.get("transaction_id")
                    ),
                    "transaction_type": transaction_type,
                    "transaction_date": _text(
                        event.get("transaction_date")
                    ),
                    "source_id": source_id,
                    "payout_id": _text(
                        event.get("payout_id")
                    ),
                    "reservation_id": _text(
                        original.get("reservation_id")
                    ),
                    "channel_reservation_id": _text(
                        original.get(
                            "channel_reservation_id"
                        )
                    ),
                    "guest": _text(
                        original.get("guest")
                    ),
                    "listing": _text(
                        original.get("listing")
                    ),
                    "account": _text(
                        original.get("account")
                    ),
                    "class": _text(
                        original.get("class")
                    ),
                    "description": (
                        f"{transaction_type.title()} of "
                        f"{_text(original.get('description'))}"
                    ),
                    "signed_amount": f"{amount:.2f}",
                    "posting_type": "Reversal",
                    "reversal_of_posting_line_id": (
                        original_line_id
                    ),
                    "classification_source": (
                        f"Posting history reversal: "
                        f"{basis_description}"
                    ),
                    "created_by": created_by,
                    "created_at": created_at,
                    "status": "Proposed",
                    "notes": "",
                }
            )

    return (
        pd.DataFrame(
            reversal_rows,
            columns=POSTING_HISTORY_COLUMNS,
        ),
        pd.DataFrame(review_rows),
    )
