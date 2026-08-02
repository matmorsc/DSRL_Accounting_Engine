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
    "gross_amount",
    "processor_fee",
    "net_amount",
    "linked_reservation_id",
    "linked_guest",
    "approval_eligible",
    "approval_status",
    "review_notes",
]

PREVIEW_COLUMNS = [
    "candidate_group_id",
    "payment_event_id",
    "source_id",
    "payout_id",
    "linked_reservation_id",
    "linked_guest",
    "validation_status",
    "original_lines_found",
    "reversal_lines_created",
    "reversal_total",
    "dispute_fee",
    "proposed_total",
    "net_amount",
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


def build_linked_dispute_approvals(
    payment_ledger: pd.DataFrame,
) -> pd.DataFrame:
    if payment_ledger.empty:
        return pd.DataFrame(columns=APPROVAL_COLUMNS)

    disputes = payment_ledger.loc[
        payment_ledger["processor"]
        .astype(str)
        .str.strip()
        .eq("Stripe")
        & payment_ledger["transaction_type"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("adjustment")
        & payment_ledger["source_id"]
        .astype(str)
        .str.strip()
        .str.startswith("du_")
    ].copy()

    rows = []
    for _, event in disputes.iterrows():
        event_id = _text(event.get("payment_event_id"))
        source_id = _text(event.get("source_id"))
        payout_id = _text(event.get("payout_id"))
        gross = _money(event.get("gross_amount"))
        fee = _money(event.get("processor_fee"))
        net = _money(event.get("net_amount"))

        group_id = _stable_id(
            "disputegrp",
            [event_id, source_id, payout_id],
        )

        valid = (
            gross < 0
            and fee >= 0
            and abs(round(gross - abs(fee), 2) - net) <= 0.02
            and bool(payout_id)
        )

        rows.append(
            {
                "candidate_group_id": group_id,
                "payment_event_id": event_id,
                "source_id": source_id,
                "payout_id": payout_id,
                "gross_amount": gross,
                "processor_fee": fee,
                "net_amount": net,
                "linked_reservation_id": "",
                "linked_guest": "",
                "approval_eligible": "Yes" if valid else "No",
                "approval_status": "Pending" if valid else "Not Eligible",
                "review_notes": (
                    "Enter the linked reservation ID and guest before approval."
                    if valid
                    else "Dispute source values failed validation."
                ),
            }
        )

    return pd.DataFrame(rows, columns=APPROVAL_COLUMNS)


def _is_reversible_original(row: pd.Series) -> bool:
    posting_type = _text(row.get("posting_type"))
    status = _text(row.get("status"))
    account = _text(row.get("account")).lower()

    if posting_type != "Original" or status not in {"", "Active"}:
        return False

    if "stripe processing fees" in account:
        return False

    return abs(_money(row.get("signed_amount"))) > 0.005


def _build_reversal_row(
    original: pd.Series,
    approval: pd.Series,
    *,
    created_at: str,
) -> dict[str, object]:
    original_line_id = _text(
        original.get("posting_line_id")
    )
    event_id = _text(
        approval.get("payment_event_id")
    )
    source_id = _text(
        approval.get("source_id")
    )

    return {
        "posting_line_id": _stable_id(
            "pl",
            [event_id, original_line_id, "dispute-reversal"],
        ),
        "posting_group_id": _stable_id(
            "pg",
            [_text(approval.get("candidate_group_id"))],
        ),
        "payment_event_id": event_id,
        "processor": "Stripe",
        "processor_account": _text(
            original.get("processor_account")
        ),
        "transaction_id": "",
        "transaction_type": "adjustment",
        "transaction_date": "",
        "source_id": source_id,
        "payout_id": _text(approval.get("payout_id")),
        "reservation_id": _text(
            original.get("reservation_id")
        ),
        "channel_reservation_id": _text(
            original.get("channel_reservation_id")
        ),
        "guest": _text(original.get("guest")),
        "listing": _text(original.get("listing")),
        "account": _text(original.get("account")),
        "class": _text(original.get("class")),
        "description": (
            "Stripe dispute reversal of "
            + _text(original.get("description"))
        ),
        "signed_amount": -_money(
            original.get("signed_amount")
        ),
        "posting_type": "Reversal",
        "reversal_of_posting_line_id": original_line_id,
        "classification_source": "Linked Stripe Dispute",
        "created_by": "DSRL Accounting Engine V11E",
        "created_at": created_at,
        "status": "Active",
        "notes": (
            "Linked Stripe dispute reversal. "
            f"Dispute source: {source_id}. "
            f"Original posting line: {original_line_id}."
        ),
    }


def _build_fee_row(
    original_rows: pd.DataFrame,
    approval: pd.Series,
    *,
    created_at: str,
) -> dict[str, object]:
    first = original_rows.iloc[0]
    event_id = _text(approval.get("payment_event_id"))
    source_id = _text(approval.get("source_id"))
    fee = _money(approval.get("processor_fee"))

    return {
        "posting_line_id": _stable_id(
            "pl",
            [event_id, source_id, "dispute-fee"],
        ),
        "posting_group_id": _stable_id(
            "pg",
            [_text(approval.get("candidate_group_id"))],
        ),
        "payment_event_id": event_id,
        "processor": "Stripe",
        "processor_account": _text(
            first.get("processor_account")
        ),
        "transaction_id": "",
        "transaction_type": "adjustment",
        "transaction_date": "",
        "source_id": source_id,
        "payout_id": _text(approval.get("payout_id")),
        "reservation_id": _text(
            approval.get("linked_reservation_id")
        ),
        "channel_reservation_id": _text(
            first.get("channel_reservation_id")
        ),
        "guest": _text(approval.get("linked_guest"))
        or _text(first.get("guest")),
        "listing": _text(first.get("listing")),
        "account": (
            "Bank Charges & Fees:"
            "Stripe Processing Fees"
        ),
        "class": _text(first.get("class"))
        or "Hospitality",
        "description": "Stripe dispute fee",
        "signed_amount": -abs(fee),
        "posting_type": "Source Event",
        "reversal_of_posting_line_id": "",
        "classification_source": "Linked Stripe Dispute",
        "created_by": "DSRL Accounting Engine V11E",
        "created_at": created_at,
        "status": "Active",
        "notes": (
            "Stripe dispute fee linked to reservation "
            f"{_text(approval.get('linked_reservation_id'))}. "
            f"Dispute source: {source_id}."
        ),
    }


def preview_linked_dispute_promotion(
    *,
    approvals: pd.DataFrame,
    existing_history: pd.DataFrame,
    tolerance: float = 0.02,
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
        valid = True
        details = []

        reservation_id = _text(
            approval.get("linked_reservation_id")
        )
        guest = _text(
            approval.get("linked_guest")
        )
        gross = _money(approval.get("gross_amount"))
        fee = _money(approval.get("processor_fee"))
        net = _money(approval.get("net_amount"))

        if _text(
            approval.get("approval_eligible")
        ) != "Yes":
            valid = False
            details.append("Approval row is not eligible.")

        if not reservation_id:
            valid = False
            details.append(
                "Linked reservation ID is required."
            )

        originals = history.loc[
            history["reservation_id"]
            .astype(str)
            .str.strip()
            .eq(reservation_id)
        ].copy()

        reversible = originals.loc[
            originals.apply(
                _is_reversible_original,
                axis=1,
            )
        ].copy()

        if reversible.empty:
            valid = False
            details.append(
                "No active reversible Original lines were found."
            )

        if guest and not originals.empty:
            history_guests = set(
                originals["guest"]
                .astype(str)
                .str.strip()
            )
            if guest not in history_guests:
                valid = False
                details.append(
                    "Linked guest does not match posting history."
                )

        reversal_rows = [
            _build_reversal_row(
                row,
                approval,
                created_at=created_at,
            )
            for _, row in reversible.iterrows()
        ]

        reversal_total = round(
            sum(
                _money(row["signed_amount"])
                for row in reversal_rows
            ),
            2,
        )

        expected_reversal = gross
        if abs(
            reversal_total - expected_reversal
        ) > tolerance:
            valid = False
            details.append(
                f"Original allocation reverses to "
                f"{reversal_total:.2f}, but dispute gross is "
                f"{gross:.2f}."
            )

        fee_row = (
            _build_fee_row(
                reversible,
                approval,
                created_at=created_at,
            )
            if not reversible.empty
            else None
        )

        history_rows = reversal_rows + (
            [fee_row] if fee_row else []
        )

        proposed_total = round(
            sum(
                _money(row["signed_amount"])
                for row in history_rows
            ),
            2,
        )

        if abs(proposed_total - net) > tolerance:
            valid = False
            details.append(
                f"Proposed total is {proposed_total:.2f}, "
                f"but Stripe net is {net:.2f}."
            )

        duplicate_count = sum(
            1
            for row in history_rows
            if row["posting_line_id"] in existing_ids
        )

        if duplicate_count not in {0, len(history_rows)}:
            valid = False
            details.append(
                "Dispute group is partially duplicated."
            )

        if valid and duplicate_count == 0:
            status = "Ready to Promote"
            lines_to_promote = len(history_rows)
            proposed_rows.extend(history_rows)
        elif valid and duplicate_count == len(history_rows):
            status = "Already Promoted"
            lines_to_promote = 0
            details.append(
                "All linked dispute lines already exist."
            )
        else:
            status = "Blocked"
            lines_to_promote = 0

        preview_rows.append(
            {
                "candidate_group_id": _text(
                    approval.get("candidate_group_id")
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
                "linked_reservation_id": reservation_id,
                "linked_guest": guest,
                "validation_status": status,
                "original_lines_found": len(originals),
                "reversal_lines_created": len(reversal_rows),
                "reversal_total": reversal_total,
                "dispute_fee": -abs(fee),
                "proposed_total": proposed_total,
                "net_amount": net,
                "duplicate_line_count": duplicate_count,
                "lines_to_promote": lines_to_promote,
                "validation_detail": (
                    " ".join(details)
                    or "All linked dispute controls passed."
                ),
            }
        )

    return (
        pd.DataFrame(preview_rows, columns=PREVIEW_COLUMNS),
        pd.DataFrame(proposed_rows, columns=HISTORY_COLUMNS),
    )


def apply_linked_dispute_promotion(
    *,
    approvals: pd.DataFrame,
    existing_history: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    preview, proposed = preview_linked_dispute_promotion(
        approvals=approvals,
        existing_history=existing_history,
    )

    blocked = preview.loc[
        preview["validation_status"]
        .astype(str)
        .eq("Blocked")
    ]
    if not blocked.empty:
        raise ValueError(
            "One or more Approved linked disputes failed validation. "
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
