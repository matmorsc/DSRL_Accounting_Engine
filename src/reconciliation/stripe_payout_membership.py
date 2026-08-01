from __future__ import annotations

import pandas as pd


def _text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def _date_text(value: object) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def apply_exact_stripe_payout_membership(
    payment_ledger: pd.DataFrame,
    membership: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = payment_ledger.copy()
    output["exact_payout_membership_applied"] = "No"

    # CSV-loaded ledgers normally hold payout_date as text. Keep the column
    # consistently textual so pandas does not reject Timestamp assignments.
    if "payout_date" not in output.columns:
        output["payout_date"] = ""
    else:
        output["payout_date"] = (
            output["payout_date"]
            .fillna("")
            .astype(str)
        )

    lookup = {
        (
            _text(row.get("processor_account")),
            _text(row.get("balance_transaction_id")),
        ): row
        for _, row in membership.iterrows()
        if _text(row.get("balance_transaction_id"))
    }

    diagnostic_rows: list[dict[str, object]] = []

    for idx, event in output.iterrows():
        if _text(event.get("processor")) != "Stripe":
            continue

        key = (
            _text(event.get("processor_account")),
            _text(event.get("transaction_id")),
        )
        match = lookup.get(key)

        if match is None:
            continue

        prior_payout = _text(event.get("payout_id"))
        exact_payout = _text(match.get("payout_id"))

        output.at[idx, "payout_id"] = exact_payout
        output.at[
            idx,
            "payout_assignment_status",
        ] = "Assigned"
        output.at[
            idx,
            "payout_assignment_method",
        ] = "Exact Stripe payout reconciliation"
        output.at[idx, "payout_date"] = _date_text(
            match.get("payout_effective_at")
        )
        output.at[
            idx,
            "exact_payout_membership_applied",
        ] = "Yes"

        diagnostic_rows.append(
            {
                "payment_event_id": _text(
                    event.get("payment_event_id")
                ),
                "transaction_id": _text(
                    event.get("transaction_id")
                ),
                "processor_account": key[0],
                "prior_payout_id": prior_payout,
                "exact_payout_id": exact_payout,
                "assignment_changed": (
                    "Yes"
                    if prior_payout != exact_payout
                    else "No"
                ),
                "reporting_category": _text(
                    match.get("reporting_category")
                ),
                "membership_net": match.get("net"),
                "ledger_net": event.get("net_amount"),
                "net_difference": round(
                    float(event.get("net_amount", 0.0))
                    - float(match.get("net", 0.0)),
                    2,
                ),
                "source_file": _text(
                    match.get("source_file")
                ),
            }
        )

    return output, pd.DataFrame(diagnostic_rows)
