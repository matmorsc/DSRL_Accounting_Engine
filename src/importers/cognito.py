from __future__ import annotations

from pathlib import Path

import pandas as pd


def find_latest_monthly_renewal(
    root: Path,
) -> Path | None:
    folder = (
        root
        / "data"
        / "raw"
        / "cognito"
        / "monthly_renewals"
    )

    if not folder.exists():
        return None

    files = [
        path
        for path in folder.iterdir()
        if path.is_file()
        and path.name.lower() != "readme.md"
        and path.suffix.lower() in {".xlsx", ".xls", ".csv"}
    ]

    if not files:
        return None

    return max(files, key=lambda path: path.stat().st_mtime)


def _read(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=str).fillna("")

    return pd.read_excel(path, dtype=str).fillna("")


def _money(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace("(", "-", regex=False)
        .str.replace(")", "", regex=False)
        .str.strip()
        .replace({"": "0"})
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(0.0).round(2)


def normalize_monthly_renewals(
    path: Path,
) -> pd.DataFrame:
    frame = _read(path)

    required = {
        "#",
        "Status",
        "Date Submitted",
        "Tenant Name",
        "Email",
        "Unit/Site #",
        "Term Start Date",
        "Term End Date",
        "Total Amount Due",
        "Payment",
    }

    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(
            f"Cognito MonthlyRenewal report missing columns: {missing}"
        )

    output = pd.DataFrame(
        {
            "renewal_submission_id": (
                frame["#"].astype(str).str.strip()
            ),
            "status": frame["Status"].astype(str).str.strip(),
            "submitted_at": pd.to_datetime(
                frame["Date Submitted"], errors="coerce"
            ),
            "tenant_name": (
                frame["Tenant Name"].astype(str).str.strip()
            ),
            "email": frame["Email"].astype(str).str.strip(),
            "unit_site": (
                frame["Unit/Site #"].astype(str).str.strip()
            ),
            "term_start_date": pd.to_datetime(
                frame["Term Start Date"], errors="coerce"
            ),
            "term_end_date": pd.to_datetime(
                frame["Term End Date"], errors="coerce"
            ),
            "total_amount_due": _money(
                frame["Total Amount Due"]
            ),
            "payment_amount": _money(frame["Payment"]),
            "source_file": path.name,
        }
    )

    return output.sort_values(
        ["submitted_at", "renewal_submission_id"]
    ).reset_index(drop=True)
