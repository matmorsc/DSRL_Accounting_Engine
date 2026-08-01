from __future__ import annotations

import pandas as pd


def _norm(value: object) -> str:
    text = str(value or "").strip().lower()
    return " ".join(text.split())


def match_legacy_payments_to_renewals(
    payment_ledger: pd.DataFrame,
    renewals: pd.DataFrame,
    amount_tolerance: float = 0.02,
    date_tolerance_days: int = 10,
) -> pd.DataFrame:
    legacy = payment_ledger.loc[
        payment_ledger["processor_account"].isin(
            ["Legacy Cognito", "Legacy Keycheck"]
        )
        & payment_ledger["transaction_type"].isin(
            ["charge", "payment"]
        )
    ].copy()

    rows: list[dict[str, object]] = []

    for _, payment in legacy.iterrows():
        amount = abs(float(payment["gross_amount"]))
        payment_date = pd.to_datetime(
            payment["transaction_date"], errors="coerce"
        )

        candidates = renewals.copy()
        candidates["amount_difference"] = (
            candidates["payment_amount"].astype(float)
            - amount
        ).abs()
        candidates["date_difference_days"] = (
            pd.to_datetime(
                candidates["submitted_at"], errors="coerce"
            ).dt.normalize()
            - payment_date.normalize()
        ).dt.days.abs()

        candidates = candidates.loc[
            candidates["amount_difference"].le(
                amount_tolerance
            )
            & candidates["date_difference_days"].le(
                date_tolerance_days
            )
        ].sort_values(
            [
                "date_difference_days",
                "amount_difference",
                "submitted_at",
            ]
        )

        if len(candidates) == 1:
            selected = candidates.iloc[0]
            status = "Exact Amount/Date Match"
            confidence = 90
        elif len(candidates) > 1:
            selected = candidates.iloc[0]
            status = "Multiple Renewal Candidates"
            confidence = 70
        else:
            selected = None
            status = "No Renewal Match"
            confidence = 0

        rows.append(
            {
                "payment_event_id": payment[
                    "payment_event_id"
                ],
                "processor_account": payment[
                    "processor_account"
                ],
                "transaction_id": payment["transaction_id"],
                "transaction_date": payment[
                    "transaction_date"
                ],
                "payment_amount": amount,
                "match_status": status,
                "confidence_score": confidence,
                "candidate_count": len(candidates),
                "renewal_submission_id": (
                    selected["renewal_submission_id"]
                    if selected is not None
                    else ""
                ),
                "tenant_name": (
                    selected["tenant_name"]
                    if selected is not None
                    else ""
                ),
                "unit_site": (
                    selected["unit_site"]
                    if selected is not None
                    else ""
                ),
                "term_start_date": (
                    selected["term_start_date"]
                    if selected is not None
                    else pd.NaT
                ),
                "total_amount_due": (
                    float(selected["total_amount_due"])
                    if selected is not None
                    else 0.0
                ),
                "date_difference_days": (
                    int(selected["date_difference_days"])
                    if selected is not None
                    else None
                ),
            }
        )

    return pd.DataFrame(rows)
