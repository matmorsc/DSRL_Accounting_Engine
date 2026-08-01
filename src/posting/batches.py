from __future__ import annotations

import pandas as pd


LODGING_ACCOUNTS = {
    "Cabin Rent - Monthly",
    "Cabin Rent - Short-Term",
    "Motel Rent - Monthly",
    "Motel Rent - Short Term",
    "RV Rent - Monthly",
    "RV Rent - Nightly",
    "Accounts Receivable (A/R)",
    "Guest Deposits - Security",
}


def _is_bank_account(account: object) -> bool:
    return "business checking" in str(account).lower()


def _eligible_stripe_inflow(row: pd.Series) -> bool:
    transaction_type = str(
        row.get("transaction_type", "")
    ).strip().lower()
    split_account = str(
        row.get("split_account", "")
    ).strip()
    memo = str(row.get("memo", "")).upper()

    if float(row.get("amount", 0.0)) <= 0:
        return False

    if transaction_type in {"payment", "sales receipt"}:
        return True

    if transaction_type == "deposit":
        return (
            "STRIPE" in memo
            or split_account in LODGING_ACCOUNTS
        )

    return False


def build_quickbooks_posting_batches(
    quickbooks_gl: pd.DataFrame,
) -> pd.DataFrame:
    required = {
        "account",
        "transaction_date",
        "transaction_type",
        "number",
        "name",
        "memo",
        "split_account",
        "amount",
        "identified_processor",
    }

    missing = sorted(required.difference(quickbooks_gl.columns))
    if missing:
        raise ValueError(
            f"QuickBooks GL missing columns for batches: {missing}"
        )

    bank_side = quickbooks_gl.loc[
        quickbooks_gl["account"].map(_is_bank_account)
    ].copy()

    rows: list[dict[str, object]] = []

    # Airbnb deposits are normally one payout per deposit line.
    airbnb = bank_side.loc[
        bank_side["transaction_type"]
        .astype(str).str.lower().eq("deposit")
        & bank_side["memo"]
        .astype(str).str.upper().str.contains(
            "AIRBNB", na=False
        )
        & bank_side["amount"].astype(float).gt(0)
    ]

    for index, row in airbnb.iterrows():
        date = pd.to_datetime(
            row["transaction_date"], errors="coerce"
        )
        rows.append(
            {
                "qb_batch_id": (
                    f"QB-AIRBNB-{date.date().isoformat()}-{index}"
                ),
                "processor": "Airbnb",
                "batch_date": date,
                "gross_inflows": float(row["amount"]),
                "processor_fees": 0.0,
                "net_posted_amount": float(row["amount"]),
                "inflow_count": 1,
                "fee_count": 0,
                "transaction_types": "Deposit",
                "names": str(row.get("name", "")),
                "memos": str(row.get("memo", "")),
                "split_accounts": str(
                    row.get("split_account", "")
                ),
                "quickbooks_references": str(
                    row.get("number", "")
                ),
            }
        )

    # Stripe historical postings often appear as payments/sales receipts
    # plus one or more separate Stripe fee expenses on the same date.
    stripe_dates = bank_side.loc[
        (
            bank_side["name"]
            .astype(str).str.upper().eq("STRIPE")
        )
        |
        (
            bank_side["split_account"]
            .astype(str).str.upper().str.contains(
                "STRIPE PROCESSING FEES", na=False
            )
        )
        |
        (
            bank_side["memo"]
            .astype(str).str.upper().str.contains(
                "ACH DEPOSIT STRIPE", na=False
            )
        ),
        "transaction_date",
    ]

    for date_value in sorted(
        pd.to_datetime(
            stripe_dates, errors="coerce"
        ).dropna().dt.normalize().unique()
    ):
        date = pd.Timestamp(date_value)
        day_rows = bank_side.loc[
            pd.to_datetime(
                bank_side["transaction_date"],
                errors="coerce",
            ).dt.normalize().eq(date)
        ].copy()

        inflows = day_rows.loc[
            day_rows.apply(_eligible_stripe_inflow, axis=1)
        ]
        fees = day_rows.loc[
            (
                day_rows["name"]
                .astype(str).str.upper().eq("STRIPE")
            )
            |
            (
                day_rows["split_account"]
                .astype(str).str.upper().str.contains(
                    "STRIPE PROCESSING FEES", na=False
                )
            )
        ]

        if inflows.empty:
            continue

        gross = round(
            inflows["amount"].astype(float).sum(), 2
        )
        fee_amount = round(
            fees["amount"].astype(float).sum(), 2
        )
        net = round(gross + fee_amount, 2)

        rows.append(
            {
                "qb_batch_id": (
                    f"QB-STRIPE-{date.date().isoformat()}"
                ),
                "processor": "Stripe",
                "batch_date": date,
                "gross_inflows": gross,
                "processor_fees": fee_amount,
                "net_posted_amount": net,
                "inflow_count": len(inflows),
                "fee_count": len(fees),
                "transaction_types": " | ".join(
                    sorted(
                        set(
                            inflows["transaction_type"]
                            .astype(str).str.strip()
                        )
                    )
                ),
                "names": " | ".join(
                    sorted(
                        {
                            str(value).strip()
                            for value in inflows["name"]
                            if str(value).strip()
                        }
                    )
                ),
                "memos": " | ".join(
                    sorted(
                        {
                            str(value).strip()
                            for value in inflows["memo"]
                            if str(value).strip()
                        }
                    )
                ),
                "split_accounts": " | ".join(
                    sorted(
                        {
                            str(value).strip()
                            for value in inflows["split_account"]
                            if str(value).strip()
                        }
                    )
                ),
                "quickbooks_references": " | ".join(
                    sorted(
                        {
                            str(value).strip()
                            for value in inflows["number"]
                            if str(value).strip()
                        }
                    )
                ),
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["batch_date", "processor", "qb_batch_id"]
    ).reset_index(drop=True)
