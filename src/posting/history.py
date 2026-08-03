from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import pandas as pd

POSTING_HISTORY_COLUMNS = [
    "posting_line_id","posting_group_id","payment_event_id","processor",
    "processor_account","transaction_id","transaction_type","transaction_date",
    "source_id","payout_id","reservation_id","channel_reservation_id","guest",
    "listing","account","class","description","signed_amount","posting_type",
    "reversal_of_posting_line_id","classification_source","created_by",
    "created_at","status","notes",
]

REQUIRED_ALLOCATION_COLUMNS = {
    "payment_event_id","payout_id","processor","processor_account",
    "transaction_id","transaction_type","transaction_date","reservation_id",
    "channel_reservation_id","guest","listing","allocation_type","account",
    "description","amount","class",
}

def _text(value):
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan","none"} else text

def _money_text(value):
    try:
        if pd.isna(value):
            return "0.00"
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "0.00"

def _date_text(value):
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%Y-%m-%d %H:%M:%S")

def _stable_id(prefix, parts):
    digest = sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"

def read_posting_history(path: Path):
    if not path.exists():
        return pd.DataFrame(columns=POSTING_HISTORY_COLUMNS)
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [c for c in POSTING_HISTORY_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"{path.name} missing columns: {missing}")
    return frame[POSTING_HISTORY_COLUMNS].copy()

def validate_posting_history(frame):
    missing = [c for c in POSTING_HISTORY_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"Posting history missing columns: {missing}")
    counts = frame["posting_line_id"].astype(str).str.strip().value_counts()
    dupes = counts.loc[counts.gt(1)].index.tolist()
    if dupes:
        raise ValueError("Duplicate posting_line_id values: " + ", ".join(dupes))

def build_proposed_posting_history(*, allocations, payment_ledger,
                                   existing_history, created_at,
                                   created_by="DSRL Accounting Engine V8"):
    missing = sorted(REQUIRED_ALLOCATION_COLUMNS.difference(allocations.columns))
    if missing:
        raise ValueError(f"Allocations missing columns: {missing}")

    ledger_lookup = {
        _text(row.get("payment_event_id")): row
        for _, row in payment_ledger.iterrows()
        if _text(row.get("payment_event_id"))
    }
    existing_ids = set(existing_history["posting_line_id"].astype(str).str.strip())
    proposed_rows, diagnostic_rows = [], []

    for _, a in allocations.iterrows():
        event_id = _text(a.get("payment_event_id"))
        ledger_row = ledger_lookup.get(event_id)
        if ledger_row is None:
            diagnostic_rows.append({
                "payment_event_id": event_id,
                "diagnostic_type": "Missing Payment Ledger Event",
                "detail": "Allocation could not be linked to payment ledger metadata.",
            })
            continue

        group_id = _stable_id("pg", [
            event_id, _text(a.get("payout_id")),
            _text(a.get("processor_account")), _text(a.get("transaction_id"))
        ])
        line_id = _stable_id("pl", [
            group_id, _text(a.get("allocation_type")), _text(a.get("account")),
            _text(a.get("class")), _text(a.get("description")),
            _money_text(a.get("amount"))
        ])

        if line_id in existing_ids:
            diagnostic_rows.append({
                "payment_event_id": event_id,
                "diagnostic_type": "Already In Posting History",
                "detail": line_id,
            })
            continue

        tx_type = _text(a.get("transaction_type")).lower()
        posting_type = "Original" if tx_type not in {
            "refund",
            "reversal",
            "dispute",
            "adjustment",
            "resolution adjustment",
            "cancellation fee",
        } else "Source Event"

        proposed_rows.append({
            "posting_line_id": line_id,
            "posting_group_id": group_id,
            "payment_event_id": event_id,
            "processor": _text(a.get("processor")),
            "processor_account": _text(a.get("processor_account")),
            "transaction_id": _text(a.get("transaction_id")),
            "transaction_type": _text(a.get("transaction_type")),
            "transaction_date": _date_text(a.get("transaction_date")),
            "source_id": _text(ledger_row.get("source_id")),
            "payout_id": _text(a.get("payout_id")),
            "reservation_id": _text(a.get("reservation_id")),
            "channel_reservation_id": _text(a.get("channel_reservation_id")),
            "guest": _text(a.get("guest")),
            "listing": _text(a.get("listing")),
            "account": _text(a.get("account")),
            "class": _text(a.get("class")),
            "description": _text(a.get("description")),
            "signed_amount": _money_text(a.get("amount")),
            "posting_type": posting_type,
            "reversal_of_posting_line_id": "",
            "classification_source": _text(a.get("match_method")) or "Payment allocation engine",
            "created_by": created_by,
            "created_at": created_at,
            "status": "Proposed",
            "notes": "",
        })

    proposed = pd.DataFrame(proposed_rows, columns=POSTING_HISTORY_COLUMNS)
    combined = pd.concat(
        [existing_history[POSTING_HISTORY_COLUMNS], proposed],
        ignore_index=True
    )
    validate_posting_history(combined)
    return proposed, pd.DataFrame(diagnostic_rows)
