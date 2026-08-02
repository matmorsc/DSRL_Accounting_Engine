from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pandas as pd

HISTORY_COLUMNS = [
    "posting_line_id", "posting_group_id", "payment_event_id", "processor",
    "processor_account", "transaction_id", "transaction_type",
    "transaction_date", "source_id", "payout_id", "reservation_id",
    "channel_reservation_id", "guest", "listing", "account", "class",
    "description", "signed_amount", "posting_type",
    "reversal_of_posting_line_id", "classification_source", "created_by",
    "created_at", "status", "notes",
]

PREVIEW_COLUMNS = [
    "candidate_group_id", "approval_status", "approval_eligible",
    "validation_status", "validation_detail", "payout_id", "source_id",
    "guest", "listing", "candidate_line_count", "candidate_total",
    "expected_effect", "remaining_difference", "duplicate_line_count",
    "lines_to_promote",
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


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _ensure_history_columns(history: pd.DataFrame) -> pd.DataFrame:
    frame = history.copy()
    for column in HISTORY_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    return frame[HISTORY_COLUMNS]


def _history_line(candidate: pd.Series, created_at: str) -> dict[str, object]:
    candidate_id = _text(candidate.get("candidate_id"))
    group_id = _text(candidate.get("candidate_group_id"))
    notes = " ".join([
        f"Candidate ID: {candidate_id}.",
        f"Allocation method: {_text(candidate.get('allocation_method'))}.",
        f"Evidence level: {_text(candidate.get('evidence_level'))}.",
        f"Evidence source: {_text(candidate.get('evidence_source'))}.",
        f"Evidence reason: {_text(candidate.get('evidence_reason'))}.",
        "Approved through Stripe seed promotion workflow.",
    ])
    return {
        "posting_line_id": _stable_id("pl", candidate_id),
        "posting_group_id": _stable_id("pg", group_id),
        "payment_event_id": _text(candidate.get("payment_event_id")),
        "processor": "Stripe",
        "processor_account": _text(candidate.get("processor_account")),
        "transaction_id": _text(candidate.get("transaction_id")),
        "transaction_type": "charge",
        "transaction_date": _text(candidate.get("transaction_date")),
        "source_id": _text(candidate.get("source_id")),
        "payout_id": _text(candidate.get("payout_id")),
        "reservation_id": _text(candidate.get("reservation_id")),
        "channel_reservation_id": _text(candidate.get("channel_reservation_id")),
        "guest": _text(candidate.get("guest")),
        "listing": _text(candidate.get("listing")),
        "account": _text(candidate.get("account")),
        "class": _text(candidate.get("class")),
        "description": _text(candidate.get("description")),
        "signed_amount": _money(candidate.get("signed_amount")),
        "posting_type": "Original",
        "reversal_of_posting_line_id": "",
        "classification_source": _text(candidate.get("allocation_method")),
        "created_by": "DSRL Accounting Engine V11D",
        "created_at": created_at,
        "status": "Active",
        "notes": notes,
    }


def preview_stripe_seed_promotion(*, approvals: pd.DataFrame, candidates: pd.DataFrame,
                                  existing_history: pd.DataFrame,
                                  tolerance: float = 0.02) -> tuple[pd.DataFrame, pd.DataFrame]:
    history = _ensure_history_columns(existing_history)
    existing_ids = set(history["posting_line_id"].astype(str).str.strip())
    preview_rows, proposed_rows = [], []
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    for _, approval in approvals.iterrows():
        if _text(approval.get("approval_status")) != "Approved":
            continue
        group_id = _text(approval.get("candidate_group_id"))
        group = candidates.loc[candidates["candidate_group_id"].astype(str).str.strip().eq(group_id)].copy()
        errors = []
        if _text(approval.get("approval_eligible")) != "Yes": errors.append("Not eligible.")
        if _text(approval.get("sign_safe")) != "Yes": errors.append("Not sign-safe.")
        if _text(approval.get("exact_match")) != "Yes": errors.append("Not an exact match.")
        remaining = _money(approval.get("remaining_difference_after_seed"))
        if abs(remaining) > tolerance: errors.append("Remaining difference is not zero.")
        if group.empty: errors.append("No candidate lines found.")
        expected_count = int(_money(approval.get("line_count")))
        if len(group) != expected_count: errors.append("Line count does not match approval.")
        candidate_total = _money(pd.to_numeric(group.get("signed_amount", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
        expected_effect = _money(approval.get("proposed_seed_effect"))
        if abs(candidate_total - expected_effect) > tolerance: errors.append("Candidate total does not match approved effect.")

        group_rows, duplicates = [], 0
        for _, candidate in group.iterrows():
            row = _history_line(candidate, created_at)
            if row["posting_line_id"] in existing_ids:
                duplicates += 1
            else:
                group_rows.append(row)
        if duplicates and group_rows:
            errors.append("Partial duplicate group; manual review required.")
        already = len(group) > 0 and duplicates == len(group)
        valid = not errors
        if valid and not already:
            proposed_rows.extend(group_rows)
        status = "Blocked" if errors else ("Already Promoted" if already else "Ready to Promote")
        preview_rows.append({
            "candidate_group_id": group_id,
            "approval_status": _text(approval.get("approval_status")),
            "approval_eligible": _text(approval.get("approval_eligible")),
            "validation_status": status,
            "validation_detail": " ".join(errors) or ("All lines already exist." if already else "All promotion controls passed."),
            "payout_id": _text(approval.get("payout_id")),
            "source_id": _text(approval.get("source_id")),
            "guest": _text(approval.get("guest")),
            "listing": _text(approval.get("listing")),
            "candidate_line_count": len(group),
            "candidate_total": candidate_total,
            "expected_effect": expected_effect,
            "remaining_difference": remaining,
            "duplicate_line_count": duplicates,
            "lines_to_promote": len(group_rows) if status == "Ready to Promote" else 0,
        })
    return pd.DataFrame(preview_rows, columns=PREVIEW_COLUMNS), pd.DataFrame(proposed_rows, columns=HISTORY_COLUMNS)


def apply_stripe_seed_promotion(*, approvals: pd.DataFrame, candidates: pd.DataFrame,
                                existing_history: pd.DataFrame,
                                tolerance: float = 0.02) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    preview, proposed = preview_stripe_seed_promotion(
        approvals=approvals, candidates=candidates,
        existing_history=existing_history, tolerance=tolerance,
    )
    if not preview.loc[preview["validation_status"].eq("Blocked")].empty:
        raise ValueError("One or more Approved groups failed validation; nothing was changed.")
    history = _ensure_history_columns(existing_history)
    updated_history = history if proposed.empty else pd.concat([history, proposed], ignore_index=True)[HISTORY_COLUMNS]
    updated_approvals = approvals.copy()
    promoted = set(preview.loc[preview["validation_status"].isin(["Ready to Promote", "Already Promoted"]), "candidate_group_id"].astype(str))
    for idx, row in updated_approvals.iterrows():
        if _text(row.get("candidate_group_id")) in promoted:
            updated_approvals.at[idx, "approval_status"] = "Promoted"
            updated_approvals.at[idx, "review_notes"] = (_text(row.get("review_notes")) + " Promoted to manual seed history.").strip()
    return preview, updated_history, updated_approvals
