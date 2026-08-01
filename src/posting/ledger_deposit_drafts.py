from __future__ import annotations

import pandas as pd


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


def combine_ledger_sources(
    *,
    persistent_history: pd.DataFrame,
    manual_seeds: pd.DataFrame,
    reversal_preview: pd.DataFrame,
) -> pd.DataFrame:
    """
    Combine the accounting ledger sources used for Phase D.

    Persistent history contributes Active rows.
    Manual seeds contribute Active rows.
    Reversal preview contributes Proposed Reversal rows only.
    """
    persistent = persistent_history.loc[
        persistent_history["status"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("active")
    ].copy()

    seeds = manual_seeds.loc[
        manual_seeds["status"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("active")
    ].copy()

    reversals = reversal_preview.loc[
        reversal_preview["status"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("proposed")
        & reversal_preview["posting_type"]
        .astype(str)
        .str.strip()
        .eq("Reversal")
    ].copy()

    persistent["ledger_source"] = "Persistent History"
    seeds["ledger_source"] = "Manual Seed"
    reversals["ledger_source"] = "Reversal Preview"

    combined = pd.concat(
        [persistent, seeds, reversals],
        ignore_index=True,
        sort=False,
    )

    combined = combined.loc[
        combined["payout_id"]
        .astype(str)
        .str.strip()
        .ne("")
    ].copy()

    duplicate_ids = (
        combined["posting_line_id"]
        .astype(str)
        .str.strip()
        .value_counts()
    )
    duplicate_ids = duplicate_ids.loc[
        duplicate_ids.gt(1)
    ].index.tolist()

    if duplicate_ids:
        raise ValueError(
            "Duplicate posting_line_id values across ledger sources: "
            + ", ".join(duplicate_ids)
        )

    combined["signed_amount"] = pd.to_numeric(
        combined["signed_amount"],
        errors="coerce",
    ).fillna(0.0).round(2)

    return combined


def build_ledger_deposit_drafts(
    *,
    ledger_lines: pd.DataFrame,
    payout_ledger: pd.DataFrame,
    tolerance: float = 0.02,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build deposit batches entirely from accounting-ledger lines.
    """
    payout_lookup = {
        _text(row.get("payout_id")): row
        for _, row in payout_ledger.iterrows()
        if _text(row.get("payout_id"))
    }

    summary_rows: list[dict[str, object]] = []
    detail_rows: list[dict[str, object]] = []

    for payout_id, payout_lines in ledger_lines.groupby(
        "payout_id",
        dropna=False,
        sort=True,
    ):
        payout_id = _text(payout_id)
        payout = payout_lookup.get(payout_id)

        grouped = (
            payout_lines.groupby(
                [
                    "account",
                    "class",
                    "description",
                    "posting_type",
                    "ledger_source",
                ],
                dropna=False,
            )
            .agg(
                amount=("signed_amount", "sum"),
                posting_line_count=("posting_line_id", "count"),
                payment_event_count=("payment_event_id", "nunique"),
                source_count=("source_id", "nunique"),
            )
            .reset_index()
        )
        grouped["amount"] = (
            pd.to_numeric(
                grouped["amount"],
                errors="coerce",
            )
            .fillna(0.0)
            .round(2)
        )
        grouped = grouped.loc[
            grouped["amount"].abs().ge(0.005)
        ].reset_index(drop=True)

        for line_number, (_, line) in enumerate(
            grouped.iterrows(),
            start=1,
        ):
            detail_rows.append(
                {
                    "payout_id": payout_id,
                    "line_number": line_number,
                    "account": _text(line.get("account")),
                    "class": _text(line.get("class")),
                    "description": _text(
                        line.get("description")
                    ),
                    "posting_type": _text(
                        line.get("posting_type")
                    ),
                    "ledger_source": _text(
                        line.get("ledger_source")
                    ),
                    "amount": _money(line.get("amount")),
                    "posting_line_count": int(
                        line.get("posting_line_count", 0)
                    ),
                    "payment_event_count": int(
                        line.get("payment_event_count", 0)
                    ),
                    "source_count": int(
                        line.get("source_count", 0)
                    ),
                }
            )

        ledger_total = round(
            grouped["amount"].sum()
            if not grouped.empty
            else 0.0,
            2,
        )

        payout_found = payout is not None
        payout_amount = (
            _money(payout.get("payout_amount"))
            if payout_found
            else 0.0
        )
        difference = round(
            ledger_total - payout_amount,
            2,
        )
        balanced = (
            payout_found
            and abs(difference) <= tolerance
        )

        missing_account_lines = int(
            payout_lines["account"]
            .astype(str)
            .str.strip()
            .eq("")
            .sum()
        )
        missing_class_lines = int(
            payout_lines["class"]
            .astype(str)
            .str.strip()
            .eq("")
            .sum()
        )

        reasons: list[str] = []
        if not payout_found:
            reasons.append(
                "Payout ID was not found in payout ledger."
            )
        if missing_account_lines:
            reasons.append(
                f"{missing_account_lines} ledger line(s) missing account."
            )
        if missing_class_lines:
            reasons.append(
                f"{missing_class_lines} ledger line(s) missing class."
            )
        if payout_found and not balanced:
            reasons.append(
                f"Ledger total differs from payout amount by {difference:.2f}."
            )

        summary_rows.append(
            {
                "payout_id": payout_id,
                "processor": (
                    _text(payout.get("processor"))
                    if payout_found
                    else ""
                ),
                "processor_account": (
                    _text(
                        payout.get("processor_account")
                    )
                    if payout_found
                    else ""
                ),
                "payout_date": (
                    _text(
                        payout.get("transaction_date")
                    )
                    if payout_found
                    else ""
                ),
                "payout_amount": payout_amount,
                "ledger_total": ledger_total,
                "difference": difference,
                "balanced": "Yes" if balanced else "No",
                "draft_status": (
                    "Ready for Review"
                    if not reasons
                    else "Review Required"
                ),
                "review_reason": " ".join(reasons),
                "ledger_line_count": len(payout_lines),
                "grouped_line_count": len(grouped),
                "payment_event_count": int(
                    payout_lines[
                        "payment_event_id"
                    ].nunique()
                ),
                "source_count": int(
                    payout_lines["source_id"].nunique()
                ),
                "persistent_line_count": int(
                    payout_lines["ledger_source"]
                    .astype(str)
                    .eq("Persistent History")
                    .sum()
                ),
                "seed_line_count": int(
                    payout_lines["ledger_source"]
                    .astype(str)
                    .eq("Manual Seed")
                    .sum()
                ),
                "reversal_line_count": int(
                    payout_lines["ledger_source"]
                    .astype(str)
                    .eq("Reversal Preview")
                    .sum()
                ),
            }
        )

    summary_columns = [
        "payout_id",
        "processor",
        "processor_account",
        "payout_date",
        "payout_amount",
        "ledger_total",
        "difference",
        "balanced",
        "draft_status",
        "review_reason",
        "ledger_line_count",
        "grouped_line_count",
        "payment_event_count",
        "source_count",
        "persistent_line_count",
        "seed_line_count",
        "reversal_line_count",
    ]

    detail_columns = [
        "payout_id",
        "line_number",
        "account",
        "class",
        "description",
        "posting_type",
        "ledger_source",
        "amount",
        "posting_line_count",
        "payment_event_count",
        "source_count",
    ]

    return (
        pd.DataFrame(
            summary_rows,
            columns=summary_columns,
        ),
        pd.DataFrame(
            detail_rows,
            columns=detail_columns,
        ),
    )


def compare_deposit_drafts(
    *,
    ledger_drafts: pd.DataFrame,
    legacy_drafts: pd.DataFrame,
) -> pd.DataFrame:
    legacy_lookup = {
        _text(row.get("payout_id")): row
        for _, row in legacy_drafts.iterrows()
        if _text(row.get("payout_id"))
    }

    rows: list[dict[str, object]] = []

    for _, ledger in ledger_drafts.iterrows():
        payout_id = _text(ledger.get("payout_id"))
        legacy = legacy_lookup.get(payout_id)

        ledger_total = _money(
            ledger.get("ledger_total")
        )
        legacy_total = (
            _money(legacy.get("draft_total"))
            if legacy is not None
            else 0.0
        )
        payout_amount = _money(
            ledger.get("payout_amount")
        )

        ledger_abs = abs(
            ledger_total - payout_amount
        )
        legacy_abs = (
            abs(legacy_total - payout_amount)
            if legacy is not None
            else None
        )

        if legacy is None:
            comparison_status = (
                "Ledger Only"
            )
        elif ledger_abs < legacy_abs:
            comparison_status = "Improved"
        elif ledger_abs > legacy_abs:
            comparison_status = "Worse"
        else:
            comparison_status = "Same"

        rows.append(
            {
                "payout_id": payout_id,
                "processor": _text(
                    ledger.get("processor")
                ),
                "payout_amount": payout_amount,
                "legacy_draft_total": legacy_total,
                "legacy_difference": (
                    round(
                        legacy_total - payout_amount,
                        2,
                    )
                    if legacy is not None
                    else ""
                ),
                "ledger_draft_total": ledger_total,
                "ledger_difference": round(
                    ledger_total - payout_amount,
                    2,
                ),
                "comparison_status": (
                    comparison_status
                ),
                "legacy_balanced": (
                    _text(legacy.get("balanced"))
                    if legacy is not None
                    else ""
                ),
                "ledger_balanced": _text(
                    ledger.get("balanced")
                ),
            }
        )

    return pd.DataFrame(rows)
