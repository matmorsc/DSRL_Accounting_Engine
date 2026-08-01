from __future__ import annotations

from hashlib import sha256

import pandas as pd


SUMMARY_COLUMNS = [
    "package_id","payout_id","processor","processor_account",
    "processor_payout_date","bank_transaction_id","bank_transaction_date",
    "bank_description","bank_amount","payout_amount","posting_total",
    "difference","bank_difference","balanced","bank_balanced",
    "review_status","confidence","comparison_status","legacy_draft_total",
    "legacy_difference","posting_line_count","payment_event_count",
    "source_count","reversal_line_count","seed_line_count","sheet_name",
    "bank_feed_label","review_notes",
]

LINE_COLUMNS = [
    "package_id","payout_id","processor","processor_account",
    "processor_payout_date","bank_transaction_id","bank_transaction_date",
    "bank_description","bank_amount","payout_amount","posting_total",
    "bank_difference","bank_balanced","review_status","confidence",
    "sheet_name","line_number","account","class","description","amount",
    "posting_type","ledger_source","posting_line_count",
    "payment_event_count","source_count","line_note",
]


def _text(value):
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def _money(value):
    try:
        if pd.isna(value):
            return 0.0
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def _date_text(value):
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%Y-%m-%d")


def _int_value(value):
    parsed = pd.to_numeric(value, errors="coerce")
    return 0 if pd.isna(parsed) else int(parsed)


def _stable_id(prefix, parts):
    digest = sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _first_existing(frame, candidates):
    for column in candidates:
        if column in frame.columns:
            return column
    return ""


def _safe_sheet_name(*, processor, display_date, payout_id, used_names):
    base = " - ".join(
        value for value in [processor or "Payout", display_date] if value
    ) or payout_id or "Payout"
    invalid = set(r'[]:*?/\\')
    cleaned = "".join(
        "_" if character in invalid else character
        for character in base
    ).strip() or "Payout"
    candidate = cleaned[:31]
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate
    suffix = _stable_id("x", [payout_id])[-5:]
    candidate = f"{cleaned[:25]}-{suffix}"[:31]
    used_names.add(candidate)
    return candidate


def _confidence(*, bank_balanced, review_status, comparison_status):
    if bank_balanced == "Yes" and review_status == "Ready for Review":
        if comparison_status in {"Same", "Improved"}:
            return "Ready"
        return "Ready - New Ledger Result"
    return "Needs Review"


def _bank_feed_label(*, bank_date, bank_description, processor, bank_amount):
    return " | ".join(
        piece for piece in [
            bank_date,
            bank_description or processor or "Payout",
            f"{bank_amount:.2f}",
        ]
        if piece
    )


def _line_note(row):
    notes = []
    posting_type = _text(row.get("posting_type"))
    ledger_source = _text(row.get("ledger_source"))
    if posting_type == "Reversal":
        notes.append("Historical reversal.")
    elif posting_type == "Adjustment":
        notes.append("Standalone adjustment.")
    if ledger_source == "Manual Seed":
        notes.append("Historical manual seed.")
    elif ledger_source == "Reversal Preview":
        notes.append("Generated from posting-history reversal.")
    elif ledger_source == "Persistent History":
        notes.append("Persistent accounting history.")
    return " ".join(notes)


def build_posting_package(
    *,
    deposit_drafts,
    deposit_lines,
    comparison,
    payout_ledger,
    bank_transactions,
):
    comparison_lookup = {
        _text(row.get("payout_id")): row
        for _, row in comparison.iterrows()
        if _text(row.get("payout_id"))
    }
    payout_lookup = {
        _text(row.get("payout_id")): row
        for _, row in payout_ledger.iterrows()
        if _text(row.get("payout_id"))
    }

    bank_id_column = _first_existing(
        bank_transactions,
        ["bank_transaction_id", "transaction_id", "id"],
    )
    bank_lookup = {}
    if bank_id_column:
        bank_lookup = {
            _text(row.get(bank_id_column)): row
            for _, row in bank_transactions.iterrows()
            if _text(row.get(bank_id_column))
        }

    used_sheet_names = set()
    summary_rows = []
    line_rows = []
    draft_lookup = {}

    for _, draft in deposit_drafts.iterrows():
        payout_id = _text(draft.get("payout_id"))
        processor = _text(draft.get("processor"))
        processor_account = _text(draft.get("processor_account"))
        processor_payout_date = _date_text(draft.get("payout_date"))
        payout_amount = _money(draft.get("payout_amount"))
        posting_total = _money(draft.get("ledger_total"))
        difference = _money(draft.get("difference"))
        balanced = _text(draft.get("balanced"))
        review_status = _text(draft.get("draft_status"))

        payout_row = payout_lookup.get(payout_id)
        bank_transaction_id = (
            _text(payout_row.get("bank_transaction_id"))
            if payout_row is not None else ""
        )
        bank_transaction_date = (
            _date_text(payout_row.get("bank_transaction_date"))
            if payout_row is not None else ""
        )
        bank_amount = (
            _money(payout_row.get("bank_amount"))
            if payout_row is not None else 0.0
        )

        bank_row = bank_lookup.get(bank_transaction_id)
        bank_description = ""
        if bank_row is not None:
            for field in ["description", "name", "memo"]:
                candidate = _text(bank_row.get(field))
                if candidate:
                    bank_description = candidate
                    break

        bank_found = bool(
            bank_transaction_id
            or bank_transaction_date
            or abs(bank_amount) > 0.005
        )

        bank_difference = round(posting_total - bank_amount, 2)
        bank_balanced = (
            "Yes"
            if bank_found and abs(bank_difference) <= 0.02
            else "No"
        )

        comparison_row = comparison_lookup.get(payout_id)
        comparison_status = (
            _text(comparison_row.get("comparison_status"))
            if comparison_row is not None else ""
        )
        legacy_total = (
            _money(comparison_row.get("legacy_draft_total"))
            if comparison_row is not None else 0.0
        )
        legacy_difference = (
            _money(comparison_row.get("legacy_difference"))
            if comparison_row is not None else 0.0
        )

        confidence = _confidence(
            bank_balanced=bank_balanced,
            review_status=review_status,
            comparison_status=comparison_status,
        )
        display_date = bank_transaction_date or processor_payout_date

        package_id = _stable_id(
            "pkg",
            [payout_id, processor, display_date, f"{bank_amount or payout_amount:.2f}"],
        )
        sheet_name = _safe_sheet_name(
            processor=processor,
            display_date=display_date,
            payout_id=payout_id,
            used_names=used_sheet_names,
        )

        reversal_count = _int_value(draft.get("reversal_line_count"))
        seed_count = _int_value(draft.get("seed_line_count"))

        notes = []
        if reversal_count:
            notes.append(f"Includes {reversal_count} reversal line(s).")
        if seed_count:
            notes.append(f"Uses {seed_count} historical seed line(s).")
        if comparison_status == "Improved":
            notes.append("Ledger-backed result improves on legacy draft.")
        elif comparison_status == "Worse":
            notes.append("Ledger-backed result is worse than legacy draft.")
        if not bank_found:
            notes.append("No matched bank transaction was found.")
        elif abs(bank_difference) > 0.02:
            notes.append(
                f"Posting total differs from bank amount by {bank_difference:.2f}."
            )
        review_reason = _text(draft.get("review_reason"))
        if review_reason:
            notes.append(review_reason)

        summary_row = {
            "package_id": package_id,
            "payout_id": payout_id,
            "processor": processor,
            "processor_account": processor_account,
            "processor_payout_date": processor_payout_date,
            "bank_transaction_id": bank_transaction_id,
            "bank_transaction_date": bank_transaction_date,
            "bank_description": bank_description,
            "bank_amount": bank_amount,
            "payout_amount": payout_amount,
            "posting_total": posting_total,
            "difference": difference,
            "bank_difference": bank_difference,
            "balanced": balanced,
            "bank_balanced": bank_balanced,
            "review_status": review_status,
            "confidence": confidence,
            "comparison_status": comparison_status,
            "legacy_draft_total": legacy_total,
            "legacy_difference": legacy_difference,
            "posting_line_count": _int_value(draft.get("ledger_line_count")),
            "payment_event_count": _int_value(draft.get("payment_event_count")),
            "source_count": _int_value(draft.get("source_count")),
            "reversal_line_count": reversal_count,
            "seed_line_count": seed_count,
            "sheet_name": sheet_name,
            "bank_feed_label": _bank_feed_label(
                bank_date=bank_transaction_date,
                bank_description=bank_description,
                processor=processor,
                bank_amount=bank_amount,
            ),
            "review_notes": " ".join(notes),
        }
        summary_rows.append(summary_row)
        draft_lookup[payout_id] = summary_row

    for _, line in deposit_lines.iterrows():
        payout_id = _text(line.get("payout_id"))
        draft = draft_lookup.get(payout_id)
        if draft is None:
            continue
        line_rows.append({
            "package_id": draft["package_id"],
            "payout_id": payout_id,
            "processor": draft["processor"],
            "processor_account": draft["processor_account"],
            "processor_payout_date": draft["processor_payout_date"],
            "bank_transaction_id": draft["bank_transaction_id"],
            "bank_transaction_date": draft["bank_transaction_date"],
            "bank_description": draft["bank_description"],
            "bank_amount": draft["bank_amount"],
            "payout_amount": draft["payout_amount"],
            "posting_total": draft["posting_total"],
            "bank_difference": draft["bank_difference"],
            "bank_balanced": draft["bank_balanced"],
            "review_status": draft["review_status"],
            "confidence": draft["confidence"],
            "sheet_name": draft["sheet_name"],
            "line_number": _int_value(line.get("line_number")),
            "account": _text(line.get("account")),
            "class": _text(line.get("class")),
            "description": _text(line.get("description")),
            "amount": _money(line.get("amount")),
            "posting_type": _text(line.get("posting_type")),
            "ledger_source": _text(line.get("ledger_source")),
            "posting_line_count": _int_value(line.get("posting_line_count")),
            "payment_event_count": _int_value(line.get("payment_event_count")),
            "source_count": _int_value(line.get("source_count")),
            "line_note": _line_note(line),
        })

    summary = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)
    lines = pd.DataFrame(line_rows, columns=LINE_COLUMNS)

    if not summary.empty:
        summary = summary.sort_values(
            [
                "review_status","processor","bank_transaction_date",
                "processor_payout_date","payout_id",
            ]
        ).reset_index(drop=True)

    if not lines.empty:
        lines = lines.sort_values(
            [
                "processor","bank_transaction_date","processor_payout_date",
                "payout_id","line_number",
            ]
        ).reset_index(drop=True)

    return summary, lines
