from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pandas as pd


HISTORY_COLUMNS = [
    "posting_line_id",
    "posting_group_id",
    "payment_event_id",
    "processor",
    "processor_account",
    "transaction_id",
    "transaction_type",
    "transaction_date",
    "source_id",
    "payout_id",
    "reservation_id",
    "channel_reservation_id",
    "guest",
    "listing",
    "account",
    "class",
    "description",
    "signed_amount",
    "posting_type",
    "reversal_of_posting_line_id",
    "classification_source",
    "created_by",
    "created_at",
    "status",
    "notes",
]

APPROVAL_COLUMNS = [
    "candidate_group_id",
    "payment_event_id",
    "source_id",
    "payout_id",
    "reservation_id",
    "channel_reservation_id",
    "guest",
    "listing",
    "property_class",
    "gross_amount",
    "processor_fee",
    "net_amount",
    "state_rate",
    "local_rate",
    "reconstructed_revenue",
    "reconstructed_state_tax",
    "reconstructed_local_tax",
    "candidate_total",
    "approval_eligible",
    "approval_status",
    "review_notes",
]

PREVIEW_COLUMNS = [
    "candidate_group_id",
    "payout_id",
    "guest",
    "listing",
    "gross_amount",
    "reconstructed_revenue",
    "reconstructed_state_tax",
    "reconstructed_local_tax",
    "processor_fee",
    "proposed_net",
    "expected_net",
    "validation_status",
    "duplicate_line_count",
    "lines_to_promote",
    "validation_detail",
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


def _rate(value: object) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _stable_id(prefix: str, parts: list[str]) -> str:
    digest = hashlib.sha256(
        "|".join(parts).encode("utf-8")
    ).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _ensure_history_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in HISTORY_COLUMNS:
        if column not in result.columns:
            result[column] = ""
    return result[HISTORY_COLUMNS]


def reconstruct_tax_allocation(
    *,
    gross_amount: float,
    state_rate: float,
    local_rate: float,
) -> tuple[float, float, float]:
    total_rate = state_rate + local_rate
    if gross_amount <= 0:
        raise ValueError("Gross amount must be positive.")
    if total_rate <= 0:
        raise ValueError("Combined tax rate must be positive.")

    approximate_revenue = gross_amount / (1 + total_rate)
    base_cents = int(round(approximate_revenue * 100))

    solutions: list[tuple[float, float, float]] = []
    for cents in range(max(0, base_cents - 10), base_cents + 11):
        revenue = round(cents / 100, 2)
        state_tax = round(revenue * state_rate, 2)
        local_tax = round(revenue * local_rate, 2)
        total = round(revenue + state_tax + local_tax, 2)
        if abs(total - gross_amount) <= 0.005:
            solutions.append((revenue, state_tax, local_tax))

    if not solutions:
        raise ValueError(
            "No exact penny-level allocation found for the configured tax rates."
        )

    # Prefer the solution nearest the algebraic revenue estimate.
    solutions.sort(key=lambda item: abs(item[0] - approximate_revenue))
    return solutions[0]


def _income_account(listing: str, property_class: str) -> str:
    text = f"{listing} {property_class}".lower()
    if "rv" in text:
        return "RV Rent - Nightly"
    if "cabin" in text:
        return "Cabin Rent - Short-Term"
    return "Motel Rent - Short Term"


def _qb_class(listing: str, property_class: str) -> str:
    text = f"{listing} {property_class}".lower()
    if "rv" in text:
        return "RV Sites"
    if "cabin" in text:
        return "Cabins"
    return "Hospitality"


def build_reconstruction_candidates(
    *,
    payment_ledger: pd.DataFrame,
    reservations: pd.DataFrame,
    tax_config: pd.DataFrame,
) -> pd.DataFrame:
    if payment_ledger.empty or reservations.empty or tax_config.empty:
        return pd.DataFrame(columns=APPROVAL_COLUMNS)

    config_row = tax_config.iloc[0]
    state_rate = _rate(config_row.get("state_rate"))
    local_rate = _rate(config_row.get("local_rate"))

    reservation_by_id = {
        _text(row.get("reservation_id")): row
        for _, row in reservations.iterrows()
        if _text(row.get("reservation_id"))
    }

    rows = []
    for _, event in payment_ledger.iterrows():
        if _text(event.get("processor")) != "Stripe":
            continue
        if _text(event.get("transaction_type")).lower() != "charge":
            continue

        reservation_id = _text(event.get("reservation_id"))
        reservation = reservation_by_id.get(reservation_id)
        if reservation is None:
            continue

        # Only candidate rows whose normalized reservation allocation is gone.
        component_total = round(
            _money(reservation.get("accommodation_revenue"))
            + _money(reservation.get("state_tax"))
            + _money(reservation.get("county_tax"))
            + _money(reservation.get("local_tax")),
            2,
        )
        if abs(component_total) > 0.005:
            continue

        gross = _money(event.get("gross_amount"))
        fee = _money(event.get("processor_fee"))
        net = _money(event.get("net_amount"))
        total_refunded = _money(reservation.get("total_refunded"))

        eligible = True
        notes = []

        if total_refunded > 0.005:
            eligible = False
            notes.append("Reservation shows a refund; reconstruction is not eligible.")

        try:
            revenue, state_tax, local_tax = reconstruct_tax_allocation(
                gross_amount=gross,
                state_rate=state_rate,
                local_rate=local_rate,
            )
        except ValueError as exc:
            eligible = False
            revenue = state_tax = local_tax = 0.0
            notes.append(str(exc))

        candidate_total = round(
            revenue + state_tax + local_tax - abs(fee),
            2,
        )
        if abs(candidate_total - net) > 0.02:
            eligible = False
            notes.append(
                f"Reconstructed net {candidate_total:.2f} does not match Stripe net {net:.2f}."
            )

        group_id = _stable_id(
            "recongrp",
            [
                _text(event.get("payment_event_id")),
                _text(event.get("source_id")),
                _text(event.get("payout_id")),
                reservation_id,
            ],
        )

        rows.append(
            {
                "candidate_group_id": group_id,
                "payment_event_id": _text(event.get("payment_event_id")),
                "source_id": _text(event.get("source_id")),
                "payout_id": _text(event.get("payout_id")),
                "reservation_id": reservation_id,
                "channel_reservation_id": _text(
                    event.get("channel_reservation_id")
                ),
                "guest": _text(event.get("guest")) or _text(reservation.get("guest")),
                "listing": _text(event.get("listing")) or _text(reservation.get("listing")),
                "property_class": _text(reservation.get("property_class")),
                "gross_amount": gross,
                "processor_fee": fee,
                "net_amount": net,
                "state_rate": state_rate,
                "local_rate": local_rate,
                "reconstructed_revenue": revenue,
                "reconstructed_state_tax": state_tax,
                "reconstructed_local_tax": local_tax,
                "candidate_total": candidate_total,
                "approval_eligible": "Yes" if eligible else "No",
                "approval_status": "Pending" if eligible else "Not Eligible",
                "review_notes": " ".join(notes),
            }
        )

    return pd.DataFrame(rows, columns=APPROVAL_COLUMNS)


def _history_rows_from_approval(
    approval: pd.Series,
    *,
    created_at: str,
) -> list[dict[str, object]]:
    group_id = _text(approval.get("candidate_group_id"))
    event_id = _text(approval.get("payment_event_id"))
    reservation_id = _text(approval.get("reservation_id"))
    listing = _text(approval.get("listing"))
    property_class = _text(approval.get("property_class"))
    qb_class = _qb_class(listing, property_class)

    allocations = [
        (
            "Revenue",
            _income_account(listing, property_class),
            listing,
            _money(approval.get("reconstructed_revenue")),
        ),
        (
            "State Tax",
            "Sales & Lodging Taxes Payable",
            "State lodging tax",
            _money(approval.get("reconstructed_state_tax")),
        ),
        (
            "Local Tax",
            "Sales & Lodging Taxes Payable",
            "Local lodging tax",
            _money(approval.get("reconstructed_local_tax")),
        ),
        (
            "Processor Fee",
            "Bank Charges & Fees:Stripe Processing Fees",
            "Stripe processing fees",
            -abs(_money(approval.get("processor_fee"))),
        ),
    ]

    rows = []
    for line_number, (allocation_type, account, description, amount) in enumerate(
        allocations, start=1
    ):
        if abs(amount) <= 0.005:
            continue

        posting_line_id = _stable_id(
            "pl",
            [
                group_id,
                str(line_number),
                allocation_type,
                f"{amount:.2f}",
            ],
        )

        rows.append(
            {
                "posting_line_id": posting_line_id,
                "posting_group_id": _stable_id("pg", [group_id]),
                "payment_event_id": event_id,
                "processor": "Stripe",
                "processor_account": "",
                "transaction_id": "",
                "transaction_type": "charge",
                "transaction_date": "",
                "source_id": _text(approval.get("source_id")),
                "payout_id": _text(approval.get("payout_id")),
                "reservation_id": reservation_id,
                "channel_reservation_id": _text(
                    approval.get("channel_reservation_id")
                ),
                "guest": _text(approval.get("guest")),
                "listing": listing,
                "account": account,
                "class": qb_class,
                "description": description,
                "signed_amount": amount,
                "posting_type": "Original",
                "reversal_of_posting_line_id": "",
                "classification_source": (
                    "Evidence-Based Tax Reconstruction"
                ),
                "created_by": "DSRL Accounting Engine V11F",
                "created_at": created_at,
                "status": "Active",
                "notes": (
                    "Original charge reconstructed from authoritative Stripe gross "
                    f"using configured tax rates state={_rate(approval.get('state_rate')):.4f} "
                    f"and local={_rate(approval.get('local_rate')):.4f}. "
                    "Reservation allocation fields were zero and no refund was recorded."
                ),
            }
        )

    return rows


def preview_reconstruction_promotion(
    *,
    approvals: pd.DataFrame,
    existing_history: pd.DataFrame,
    tolerance: float = 0.02,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    history = _ensure_history_columns(existing_history)
    existing_ids = set(
        history["posting_line_id"].astype(str).str.strip()
    )

    approved = (
        approvals.loc[
            approvals["approval_status"]
            .astype(str)
            .str.strip()
            .eq("Approved")
        ].copy()
        if not approvals.empty
        else pd.DataFrame()
    )

    preview_rows = []
    proposed_rows = []
    created_at = datetime.now(
        timezone.utc
    ).replace(microsecond=0).isoformat()

    for _, approval in approved.iterrows():
        valid = True
        details = []

        if _text(approval.get("approval_eligible")) != "Yes":
            valid = False
            details.append("Approval row is not eligible.")

        proposed = _history_rows_from_approval(
            approval,
            created_at=created_at,
        )

        proposed_net = round(
            sum(_money(row["signed_amount"]) for row in proposed),
            2,
        )
        expected_net = _money(approval.get("net_amount"))

        if abs(proposed_net - expected_net) > tolerance:
            valid = False
            details.append(
                f"Proposed net {proposed_net:.2f} does not match Stripe net {expected_net:.2f}."
            )

        duplicate_count = sum(
            1
            for row in proposed
            if row["posting_line_id"] in existing_ids
        )

        if duplicate_count not in {0, len(proposed)}:
            valid = False
            details.append("Reconstruction group is partially duplicated.")

        if valid and duplicate_count == 0:
            status = "Ready to Promote"
            lines_to_promote = len(proposed)
            proposed_rows.extend(proposed)
        elif valid and duplicate_count == len(proposed):
            status = "Already Promoted"
            lines_to_promote = 0
            details.append("All reconstruction lines already exist.")
        else:
            status = "Blocked"
            lines_to_promote = 0

        preview_rows.append(
            {
                "candidate_group_id": _text(
                    approval.get("candidate_group_id")
                ),
                "payout_id": _text(approval.get("payout_id")),
                "guest": _text(approval.get("guest")),
                "listing": _text(approval.get("listing")),
                "gross_amount": _money(approval.get("gross_amount")),
                "reconstructed_revenue": _money(
                    approval.get("reconstructed_revenue")
                ),
                "reconstructed_state_tax": _money(
                    approval.get("reconstructed_state_tax")
                ),
                "reconstructed_local_tax": _money(
                    approval.get("reconstructed_local_tax")
                ),
                "processor_fee": _money(approval.get("processor_fee")),
                "proposed_net": proposed_net,
                "expected_net": expected_net,
                "validation_status": status,
                "duplicate_line_count": duplicate_count,
                "lines_to_promote": lines_to_promote,
                "validation_detail": (
                    " ".join(details)
                    or "All reconstruction controls passed."
                ),
            }
        )

    return (
        pd.DataFrame(preview_rows, columns=PREVIEW_COLUMNS),
        pd.DataFrame(proposed_rows, columns=HISTORY_COLUMNS),
    )


def apply_reconstruction_promotion(
    *,
    approvals: pd.DataFrame,
    existing_history: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    preview, proposed = preview_reconstruction_promotion(
        approvals=approvals,
        existing_history=existing_history,
    )

    blocked = preview.loc[
        preview["validation_status"].astype(str).eq("Blocked")
    ]
    if not blocked.empty:
        raise ValueError(
            "One or more Approved reconstruction groups failed validation. "
            "No history was modified."
        )

    history = _ensure_history_columns(existing_history)
    updated_history = (
        pd.concat(
            [history, proposed],
            ignore_index=True,
            sort=False,
        )[HISTORY_COLUMNS]
        if not proposed.empty
        else history
    )

    updated_approvals = approvals.copy()
    completed = set(
        preview.loc[
            preview["validation_status"].isin(
                ["Ready to Promote", "Already Promoted"]
            ),
            "candidate_group_id",
        ].astype(str)
    )

    for index, row in updated_approvals.iterrows():
        if _text(row.get("candidate_group_id")) in completed:
            updated_approvals.at[
                index, "approval_status"
            ] = "Promoted"

    return preview, updated_history, updated_approvals
