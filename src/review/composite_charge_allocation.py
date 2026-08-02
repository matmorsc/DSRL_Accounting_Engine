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

PREVIEW_COLUMNS = [
    "composite_group_id",
    "group_name",
    "payment_event_id",
    "source_id",
    "payout_id",
    "gross_amount",
    "processor_fee",
    "net_amount",
    "allocation_line_count",
    "allocation_total",
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


def validate_composite_group(
    *,
    approval: pd.Series,
    allocations: pd.DataFrame,
    payment_ledger: pd.DataFrame,
    tolerance: float = 0.02,
) -> tuple[bool, list[str], pd.Series | None]:
    valid = True
    details: list[str] = []

    event_id = _text(approval.get("payment_event_id"))
    source_id = _text(approval.get("source_id"))
    payout_id = _text(approval.get("payout_id"))

    if _text(approval.get("approval_eligible")) != "Yes":
        valid = False
        details.append("Approval row is not eligible.")

    event_rows = payment_ledger.loc[
        payment_ledger["payment_event_id"]
        .astype(str)
        .str.strip()
        .eq(event_id)
    ].copy() if not payment_ledger.empty else pd.DataFrame()

    if len(event_rows) != 1:
        valid = False
        details.append(
            f"Expected exactly one payment event; found {len(event_rows)}."
        )
        event = None
    else:
        event = event_rows.iloc[0]

        if _text(event.get("source_id")) != source_id:
            valid = False
            details.append("Source ID does not match payment ledger.")

        if _text(event.get("payout_id")) != payout_id:
            valid = False
            details.append("Payout ID does not match payment ledger.")

        gross = _money(event.get("gross_amount"))
        fee = _money(event.get("processor_fee"))
        net = _money(event.get("net_amount"))

        if abs(gross - _money(approval.get("gross_amount"))) > tolerance:
            valid = False
            details.append("Gross amount does not match payment ledger.")

        if abs(fee - _money(approval.get("processor_fee"))) > tolerance:
            valid = False
            details.append("Processor fee does not match payment ledger.")

        if abs(net - _money(approval.get("net_amount"))) > tolerance:
            valid = False
            details.append("Net amount does not match payment ledger.")

    if allocations.empty:
        valid = False
        details.append("No allocation rows were found.")

    allocation_total = round(
        pd.to_numeric(
            allocations.get("signed_amount", pd.Series(dtype=float)),
            errors="coerce",
        ).fillna(0.0).sum(),
        2,
    )

    expected_net = _money(approval.get("net_amount"))
    if abs(allocation_total - expected_net) > tolerance:
        valid = False
        details.append(
            f"Allocation total {allocation_total:.2f} "
            f"does not match Stripe net {expected_net:.2f}."
        )

    expected_count = int(_money(approval.get("allocation_line_count")))
    if len(allocations) != expected_count:
        valid = False
        details.append(
            "Allocation line count does not match approval."
        )

    return valid, details, event


def _build_history_row(
    allocation: pd.Series,
    approval: pd.Series,
    event: pd.Series,
    *,
    created_at: str,
) -> dict[str, object]:
    group_id = _text(approval.get("composite_group_id"))
    line_id = _text(allocation.get("allocation_line_id"))

    return {
        "posting_line_id": _stable_id(
            "pl",
            [group_id, line_id],
        ),
        "posting_group_id": _stable_id(
            "pg",
            [group_id],
        ),
        "payment_event_id": _text(
            approval.get("payment_event_id")
        ),
        "processor": "Stripe",
        "processor_account": _text(
            event.get("processor_account")
        ),
        "transaction_id": _text(
            event.get("transaction_id")
        ),
        "transaction_type": "charge",
        "transaction_date": _text(
            event.get("transaction_date")
        ),
        "source_id": _text(
            approval.get("source_id")
        ),
        "payout_id": _text(
            approval.get("payout_id")
        ),
        "reservation_id": _text(
            allocation.get("reservation_id")
        ),
        "channel_reservation_id": _text(
            allocation.get("channel_reservation_id")
        ),
        "guest": _text(
            allocation.get("guest")
        ),
        "listing": _text(
            allocation.get("listing")
        ),
        "account": _text(
            allocation.get("account")
        ),
        "class": _text(
            allocation.get("class")
        ),
        "description": _text(
            allocation.get("description")
        ),
        "signed_amount": _money(
            allocation.get("signed_amount")
        ),
        "posting_type": "Original",
        "reversal_of_posting_line_id": "",
        "classification_source": "Composite Charge Allocation",
        "created_by": "DSRL Accounting Engine V11G",
        "created_at": created_at,
        "status": "Active",
        "notes": (
            f"Composite payment allocation: "
            f"{_text(approval.get('group_name'))}. "
            f"Allocation line: {line_id}. "
            "Amounts were supplied from the supporting group invoice "
            "and validated to Stripe net."
        ),
    }


def preview_composite_promotion(
    *,
    approvals: pd.DataFrame,
    allocations: pd.DataFrame,
    payment_ledger: pd.DataFrame,
    existing_history: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    history = _ensure_history_columns(existing_history)
    existing_ids = set(
        history["posting_line_id"]
        .astype(str)
        .str.strip()
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
        group_id = _text(
            approval.get("composite_group_id")
        )
        group_allocations = allocations.loc[
            allocations["composite_group_id"]
            .astype(str)
            .str.strip()
            .eq(group_id)
        ].copy()

        valid, details, event = validate_composite_group(
            approval=approval,
            allocations=group_allocations,
            payment_ledger=payment_ledger,
        )

        history_rows = []
        if event is not None:
            history_rows = [
                _build_history_row(
                    allocation,
                    approval,
                    event,
                    created_at=created_at,
                )
                for _, allocation in group_allocations.iterrows()
            ]

        duplicate_count = sum(
            1
            for row in history_rows
            if row["posting_line_id"] in existing_ids
        )

        if duplicate_count not in {0, len(history_rows)}:
            valid = False
            details.append(
                "Composite group is partially duplicated."
            )

        if valid and duplicate_count == 0:
            status = "Ready to Promote"
            lines_to_promote = len(history_rows)
            proposed_rows.extend(history_rows)
        elif valid and duplicate_count == len(history_rows):
            status = "Already Promoted"
            lines_to_promote = 0
            details.append(
                "All composite allocation lines already exist."
            )
        else:
            status = "Blocked"
            lines_to_promote = 0

        preview_rows.append(
            {
                "composite_group_id": group_id,
                "group_name": _text(
                    approval.get("group_name")
                ),
                "payment_event_id": _text(
                    approval.get("payment_event_id")
                ),
                "source_id": _text(
                    approval.get("source_id")
                ),
                "payout_id": _text(
                    approval.get("payout_id")
                ),
                "gross_amount": _money(
                    approval.get("gross_amount")
                ),
                "processor_fee": _money(
                    approval.get("processor_fee")
                ),
                "net_amount": _money(
                    approval.get("net_amount")
                ),
                "allocation_line_count": len(
                    group_allocations
                ),
                "allocation_total": round(
                    pd.to_numeric(
                        group_allocations.get(
                            "signed_amount",
                            pd.Series(dtype=float),
                        ),
                        errors="coerce",
                    ).fillna(0.0).sum(),
                    2,
                ),
                "validation_status": status,
                "duplicate_line_count": duplicate_count,
                "lines_to_promote": lines_to_promote,
                "validation_detail": (
                    " ".join(details)
                    or "All composite allocation controls passed."
                ),
            }
        )

    return (
        pd.DataFrame(preview_rows, columns=PREVIEW_COLUMNS),
        pd.DataFrame(proposed_rows, columns=HISTORY_COLUMNS),
    )


def apply_composite_promotion(
    *,
    approvals: pd.DataFrame,
    allocations: pd.DataFrame,
    payment_ledger: pd.DataFrame,
    existing_history: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    preview, proposed = preview_composite_promotion(
        approvals=approvals,
        allocations=allocations,
        payment_ledger=payment_ledger,
        existing_history=existing_history,
    )

    blocked = preview.loc[
        preview["validation_status"]
        .astype(str)
        .eq("Blocked")
    ]
    if not blocked.empty:
        raise ValueError(
            "One or more Approved composite groups failed validation. "
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
            "composite_group_id",
        ].astype(str)
    )

    for index, row in updated_approvals.iterrows():
        if _text(row.get("composite_group_id")) in completed:
            updated_approvals.at[
                index, "approval_status"
            ] = "Promoted"

    return preview, updated_history, updated_approvals
