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


def _date_key(value: object) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _find_ledger_row(
    group: pd.DataFrame,
    payment_ledger: pd.DataFrame,
) -> pd.Series | None:
    first = group.iloc[0]

    candidates = payment_ledger.loc[
        payment_ledger["payment_event_id"]
        .astype(str)
        .str.strip()
        .eq(_text(first.get("payment_event_id")))
    ].copy()

    if candidates.empty:
        return None

    # payment_event_id is not guaranteed unique for Airbnb.
    # Refine with the fields that define the posting group.
    for column, value in [
        ("transaction_type", _text(first.get("transaction_type"))),
        ("payout_id", _text(first.get("payout_id"))),
        ("transaction_id", _text(first.get("transaction_id"))),
    ]:
        if column not in candidates.columns or not value:
            continue

        refined = candidates.loc[
            candidates[column]
            .astype(str)
            .str.strip()
            .eq(value)
        ]

        if not refined.empty:
            candidates = refined

    if (
        "transaction_date" in candidates.columns
        and _text(first.get("transaction_date"))
    ):
        target_date = _date_key(
            first.get("transaction_date")
        )
        date_match = candidates.loc[
            candidates["transaction_date"]
            .apply(_date_key)
            .eq(target_date)
        ]
        if not date_match.empty:
            candidates = date_match

    if len(candidates) != 1:
        return None

    return candidates.iloc[0]


def build_posting_history_review(
    *,
    proposed_history: pd.DataFrame,
    payment_ledger: pd.DataFrame,
    tolerance: float = 0.02,
) -> pd.DataFrame:
    """
    One review row per deterministic posting group.

    payment_event_id is not unique for all processors, particularly Airbnb
    reservation and adjustment rows sharing one confirmation code.
    """
    rows: list[dict[str, object]] = []

    for posting_group_id, group in proposed_history.groupby(
        "posting_group_id",
        dropna=False,
        sort=True,
    ):
        posting_group_id = _text(posting_group_id)
        ledger = _find_ledger_row(
            group,
            payment_ledger,
        )

        posting_types = sorted(
            {
                _text(value)
                for value in group["posting_type"]
                if _text(value)
            }
        )
        signed_total = round(
            pd.to_numeric(
                group["signed_amount"],
                errors="coerce",
            )
            .fillna(0.0)
            .sum(),
            2,
        )

        ledger_net = (
            _money(ledger.get("net_amount"))
            if ledger is not None
            else 0.0
        )
        difference = round(
            signed_total - ledger_net,
            2,
        )

        missing_account_lines = int(
            group["account"]
            .astype(str)
            .str.strip()
            .eq("")
            .sum()
        )
        missing_class_lines = int(
            group["class"]
            .astype(str)
            .str.strip()
            .eq("")
            .sum()
        )

        original_only = posting_types == ["Original"]
        ledger_found = ledger is not None
        balanced = (
            ledger_found
            and abs(difference) <= tolerance
        )

        reasons: list[str] = []

        if not ledger_found:
            reasons.append(
                "Posting group could not be uniquely linked to payment ledger."
            )
        if not original_only:
            reasons.append(
                "Contains Source Event lines; excluded until Phase C."
            )
        if missing_account_lines:
            reasons.append(
                f"{missing_account_lines} line(s) missing account."
            )
        if missing_class_lines:
            reasons.append(
                f"{missing_class_lines} line(s) missing class."
            )
        if ledger_found and not balanced:
            reasons.append(
                f"Posting total differs from event net by {difference:.2f}."
            )

        review_status = (
            "Ready for Promotion"
            if (
                original_only
                and ledger_found
                and balanced
                and missing_account_lines == 0
                and missing_class_lines == 0
            )
            else (
                "Excluded - Source Event"
                if not original_only
                else "Review Required"
            )
        )

        first = group.iloc[0]

        rows.append(
            {
                "posting_group_id": posting_group_id,
                "payment_event_id": _text(
                    first.get("payment_event_id")
                ),
                "processor": _text(
                    first.get("processor")
                ),
                "processor_account": _text(
                    first.get("processor_account")
                ),
                "transaction_id": _text(
                    first.get("transaction_id")
                ),
                "transaction_type": _text(
                    first.get("transaction_type")
                ),
                "transaction_date": _text(
                    first.get("transaction_date")
                ),
                "source_id": _text(
                    first.get("source_id")
                ),
                "payout_id": _text(
                    first.get("payout_id")
                ),
                "guest": _text(first.get("guest")),
                "listing": _text(
                    first.get("listing")
                ),
                "posting_types": " | ".join(
                    posting_types
                ),
                "posting_line_count": len(group),
                "posting_total": signed_total,
                "payment_event_net": ledger_net,
                "difference": difference,
                "missing_account_lines": (
                    missing_account_lines
                ),
                "missing_class_lines": (
                    missing_class_lines
                ),
                "review_status": review_status,
                "review_reason": " ".join(reasons),
                "approved_for_promotion": (
                    "Pending"
                    if review_status
                    == "Ready for Promotion"
                    else "No"
                ),
                "review_notes": "",
            }
        )

    columns = [
        "posting_group_id",
        "payment_event_id",
        "processor",
        "processor_account",
        "transaction_id",
        "transaction_type",
        "transaction_date",
        "source_id",
        "payout_id",
        "guest",
        "listing",
        "posting_types",
        "posting_line_count",
        "posting_total",
        "payment_event_net",
        "difference",
        "missing_account_lines",
        "missing_class_lines",
        "review_status",
        "review_reason",
        "approved_for_promotion",
        "review_notes",
    ]

    return pd.DataFrame(
        rows,
        columns=columns,
    ).sort_values(
        [
            "review_status",
            "processor",
            "transaction_date",
            "posting_group_id",
        ]
    ).reset_index(drop=True)
