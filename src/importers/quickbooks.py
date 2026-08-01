from __future__ import annotations

from pathlib import Path

import pandas as pd


INCOME_ACCOUNTS = {
    "Cabin Rent - Monthly",
    "Cabin Rent - Short-Term",
    "Cancellations",
    "Coupon Code",
    "Motel Rent - Monthly",
    "Motel Rent - Short Term",
    "Refunds",
    "RV Rent - Monthly",
    "RV Rent - Nightly",
}

PROCESSOR_TERMS = {
    "STRIPE": "Stripe",
    "AIRBNB": "Airbnb",
}


def _read_excel_without_headers(path: Path) -> pd.DataFrame:
    return pd.read_excel(
        path,
        header=None,
        dtype=object,
    ).fillna("")


def _find_general_ledger(paths: list[Path]) -> Path:
    candidates = [
        path
        for path in paths
        if "general" in path.name.lower()
        and "ledger" in path.name.lower()
        and path.suffix.lower() in {".xlsx", ".xls"}
    ]

    if not candidates:
        raise FileNotFoundError(
            "No QuickBooks General Ledger workbook found."
        )

    return max(
        candidates,
        key=lambda path: path.stat().st_mtime,
    )


def _money(value: object) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0

    text = (
        text.replace("$", "")
        .replace(",", "")
        .replace("(", "-")
        .replace(")", "")
    )

    try:
        return round(float(text), 2)
    except ValueError:
        return 0.0


def _date(value: object) -> pd.Timestamp | pd.NaT:
    return pd.to_datetime(value, errors="coerce")


def _processor(description: str) -> str:
    upper = str(description).upper()

    for term, processor in PROCESSOR_TERMS.items():
        if term in upper:
            return processor

    return ""


def normalize_quickbooks_gl(
    paths: list[Path],
) -> pd.DataFrame:
    path = _find_general_ledger(paths)
    raw = _read_excel_without_headers(path)

    rows: list[dict[str, object]] = []
    current_account = ""

    for _, row in raw.iterrows():
        values = list(row)

        first = str(values[0] if len(values) > 0 else "").strip()
        second = str(values[1] if len(values) > 1 else "").strip()

        # QuickBooks report account headings commonly appear as a single
        # populated account-name cell followed by blank transaction columns.
        potential_account = first or second

        if (
            potential_account
            and potential_account in INCOME_ACCOUNTS
        ):
            current_account = potential_account
            continue

        # Transaction layout observed in the uploaded GL:
        # Account | Date | Transaction Type | Num | Name | Memo |
        # Split Account | Amount | Balance
        transaction_account = second or current_account
        transaction_date = _date(
            values[2] if len(values) > 2 else ""
        )

        if pd.isna(transaction_date):
            continue

        transaction_type = str(
            values[3] if len(values) > 3 else ""
        ).strip()
        number = str(
            values[4] if len(values) > 4 else ""
        ).strip()
        name = str(
            values[5] if len(values) > 5 else ""
        ).strip()
        memo = str(
            values[6] if len(values) > 6 else ""
        ).strip()
        split_account = str(
            values[7] if len(values) > 7 else ""
        ).strip()
        amount = _money(
            values[8] if len(values) > 8 else 0
        )

        description = " | ".join(
            value
            for value in [name, memo, split_account]
            if value
        )

        rows.append(
            {
                "source_file": path.name,
                "account": transaction_account,
                "transaction_date": transaction_date,
                "transaction_type": transaction_type,
                "number": number,
                "name": name,
                "memo": memo,
                "split_account": split_account,
                "amount": amount,
                "identified_processor": _processor(
                    description
                ),
                "is_income_account": (
                    transaction_account
                    in INCOME_ACCOUNTS
                ),
                "is_bank_deposit": (
                    transaction_type.lower()
                    == "deposit"
                ),
            }
        )

    output = pd.DataFrame(rows)

    if output.empty:
        raise ValueError(
            "The QuickBooks General Ledger could not be parsed."
        )

    return output.sort_values(
        ["transaction_date", "account", "amount"]
    ).reset_index(drop=True)
