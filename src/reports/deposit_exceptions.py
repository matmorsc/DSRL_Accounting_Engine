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


def build_deposit_exception_review(
    *,
    deposit_drafts: pd.DataFrame,
    draft_lines: pd.DataFrame,
    allocation_diagnostics: pd.DataFrame,
    payout_ledger: pd.DataFrame,
    payment_ledger: pd.DataFrame,
) -> pd.DataFrame:
    exceptions = deposit_drafts.loc[
        deposit_drafts["draft_status"]
        .astype(str)
        .str.strip()
        .ne("Ready for Review")
        |
        deposit_drafts["balanced"]
        .astype(str)
        .str.strip()
        .ne("Yes")
    ].copy()

    rows: list[dict[str, object]] = []

    for _, draft in exceptions.iterrows():
        payout_id = _text(draft.get("payout_id"))

        payout_lines = draft_lines.loc[
            draft_lines["payout_id"]
            .astype(str)
            .str.strip()
            .eq(payout_id)
        ]

        diagnostics = allocation_diagnostics.loc[
            allocation_diagnostics["payout_id"]
            .astype(str)
            .str.strip()
            .eq(payout_id)
        ]

        payout = payout_ledger.loc[
            payout_ledger["payout_id"]
            .astype(str)
            .str.strip()
            .eq(payout_id)
        ]

        events = payment_ledger.loc[
            payment_ledger["payout_id"]
            .astype(str)
            .str.strip()
            .eq(payout_id)
        ]

        diagnostic_types = sorted(
            {
                _text(value)
                for value in diagnostics.get(
                    "diagnostic_type",
                    pd.Series(dtype=str),
                )
                if _text(value)
            }
        )

        if payout_lines.empty:
            primary_issue = "No allocated draft lines"
        elif "Unlinked Payment Event" in diagnostic_types:
            primary_issue = "Unlinked payment events"
        elif "Missing Fee Account" in diagnostic_types:
            primary_issue = "Missing account mapping"
        elif "Allocation Warning" in diagnostic_types:
            primary_issue = "Allocation basis warning"
        elif _money(draft.get("difference")) != 0:
            primary_issue = "Unexplained payout difference"
        else:
            primary_issue = "Review required"

        payout_row = (
            payout.iloc[0]
            if not payout.empty
            else pd.Series(dtype=object)
        )

        rows.append(
            {
                "payout_id": payout_id,
                "processor": _text(
                    draft.get("processor")
                ),
                "deposit_date": draft.get("deposit_date"),
                "bank_amount": _money(
                    draft.get("bank_amount")
                ),
                "draft_total": _money(
                    draft.get("draft_total")
                ),
                "difference": _money(
                    draft.get("difference")
                ),
                "primary_issue": primary_issue,
                "draft_review_reason": _text(
                    draft.get("review_reason")
                ),
                "diagnostic_types": " | ".join(
                    diagnostic_types
                ),
                "diagnostic_count": len(diagnostics),
                "payment_event_count": int(
                    events["payment_event_id"].nunique()
                )
                if "payment_event_id" in events.columns
                else len(events),
                "draft_line_count": len(payout_lines),
                "payout_allocation_status": _text(
                    payout_row.get("allocation_status")
                ),
                "payout_allocation_difference": _money(
                    payout_row.get("allocation_difference")
                ),
                "bank_match_status": _text(
                    payout_row.get("bank_match_status")
                ),
                "recommended_next_action": {
                    "No allocated draft lines":
                        "Research or match payment events.",
                    "Unlinked payment events":
                        "Review Stripe/Cognito candidate matches.",
                    "Missing account mapping":
                        "Confirm QuickBooks account mapping.",
                    "Allocation basis warning":
                        "Review extension, modification, or extra charge.",
                    "Unexplained payout difference":
                        "Compare payment-event net to payout detail.",
                    "Review required":
                        "Review source data and diagnostics.",
                }[primary_issue],
            }
        )

    columns = [
        "payout_id",
        "processor",
        "deposit_date",
        "bank_amount",
        "draft_total",
        "difference",
        "primary_issue",
        "draft_review_reason",
        "diagnostic_types",
        "diagnostic_count",
        "payment_event_count",
        "draft_line_count",
        "payout_allocation_status",
        "payout_allocation_difference",
        "bank_match_status",
        "recommended_next_action",
    ]

    return pd.DataFrame(rows, columns=columns).sort_values(
        ["primary_issue", "difference"],
        ascending=[True, False],
    ).reset_index(drop=True)
