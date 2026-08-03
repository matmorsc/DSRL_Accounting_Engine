from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path, dtype=str, keep_default_na=False)

    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype=str).fillna("")

    raise ValueError(f"Unsupported file type: {path}")


def _money(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace("(", "-", regex=False)
        .str.replace(")", "", regex=False)
        .replace({"": "0", "–": "0", "-": "0"})
    )

    return pd.to_numeric(cleaned, errors="coerce").fillna(0.0).round(2)


def _dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _clean_identifier(series: pd.Series) -> pd.Series:
    cleaned = series.astype(str).str.strip()
    return cleaned.replace({"–": "", "-": "", "nan": ""})


def _property_class(listing: str) -> str:
    value = str(listing).lower()

    if "rv" in value:
        return "RV"

    if "cabin" in value or "a-frame" in value or "a frame" in value:
        return "Cabin"

    return "Motel"


def _income_account(
    property_class: str,
    nights: int,
    monthly_threshold: int,
    income_accounts: dict[str, str],
) -> str:
    monthly = nights >= monthly_threshold

    keys = {
        ("Cabin", True): "cabin_monthly",
        ("Cabin", False): "cabin_short_term",
        ("Motel", True): "motel_monthly",
        ("Motel", False): "motel_short_term",
        ("RV", True): "rv_monthly",
        ("RV", False): "rv_nightly",
    }

    return income_accounts[keys[(property_class, monthly)]]


def normalize_guesty(
    path: Path,
    monthly_threshold: int,
    income_accounts: dict[str, str],
) -> pd.DataFrame:
    frame = _read_table(path)

    required = {
        "GUEST",
        "LISTING'S NICKNAME",
        "CONFIRMATION DATE",
        "CHECK-IN",
        "CHECK-OUT",
        "SOURCE",
        "ACCOMMODATION FARE",
        "TOTAL TAXES",
        "STATE TAX",
        "COUNTY TAX",
        "LOCAL TAX",
        "TOTAL PAYOUT",
        "BALANCE DUE",
        "PAYMENT METHOD",
        "TOTAL PAID",
        "TOTAL REFUNDED",
        "CHANNEL RESERVATION ID",
        "RESERVATION ID",
    }

    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Guesty export missing columns: {missing}")

    confirmation_date = _dates(frame["CONFIRMATION DATE"])
    check_in = _dates(frame["CHECK-IN"])
    check_out = _dates(frame["CHECK-OUT"])

    nights = (
        (check_out.dt.normalize() - check_in.dt.normalize())
        .dt.days.fillna(0)
        .astype(int)
    )

    property_class = frame["LISTING'S NICKNAME"].map(_property_class)

    income_account = pd.Series(
        [
            _income_account(
                cls,
                int(stay_nights),
                monthly_threshold,
                income_accounts,
            )
            for cls, stay_nights in zip(property_class, nights)
        ],
        index=frame.index,
    )

    output = pd.DataFrame(
        {
            "reservation_id": _clean_identifier(frame["RESERVATION ID"]),
            "channel_reservation_id": _clean_identifier(
                frame["CHANNEL RESERVATION ID"]
            ),
            "guest": frame["GUEST"].astype(str).str.strip(),
            "listing": frame["LISTING'S NICKNAME"].astype(str).str.strip(),
            "property_class": property_class,
            "source": frame["SOURCE"].astype(str).str.strip(),
            "payment_method": frame["PAYMENT METHOD"].astype(str).str.strip(),
            "confirmation_date": confirmation_date,
            "check_in": check_in,
            "check_out": check_out,
            "nights": nights,
            "stay_type": nights.map(
                lambda value: (
                    "Monthly"
                    if int(value) >= monthly_threshold
                    else "Short-Term"
                )
            ),
            "income_account": income_account,
            "accommodation_revenue": _money(
                frame["ACCOMMODATION FARE"]
            ),
            "total_taxes": _money(frame["TOTAL TAXES"]),
            "state_tax": _money(frame["STATE TAX"]),
            "county_tax": _money(frame["COUNTY TAX"]),
            "local_tax": _money(frame["LOCAL TAX"]),
            "total_payout": _money(frame["TOTAL PAYOUT"]),
            "balance_due": _money(frame["BALANCE DUE"]),
            "total_paid": _money(frame["TOTAL PAID"]),
            "total_refunded": _money(frame["TOTAL REFUNDED"]),
            "source_file": path.name,
        }
    )

    duplicate_ids = output.loc[
        output["reservation_id"].ne("")
        & output["reservation_id"].duplicated(keep=False),
        "reservation_id",
    ].unique()

    if len(duplicate_ids):
        raise ValueError(
            "Guesty contains duplicate reservation IDs: "
            + ", ".join(duplicate_ids[:10])
        )

    return output.sort_values(
        ["confirmation_date", "reservation_id"],
        na_position="last",
    ).reset_index(drop=True)


def normalize_stripe(path: Path, account_name: str) -> pd.DataFrame:
    frame = _read_table(path)

    required = {
        "id",
        "Type",
        "Source",
        "Amount",
        "Fee",
        "Net",
        "Created (UTC)",
        "Available On (UTC)",
    }

    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"{account_name} Stripe export missing: {missing}")

    output = pd.DataFrame(
        {
            "processor": "Stripe",
            "processor_account": account_name,
            "transaction_id": _clean_identifier(frame["id"]),
            "transaction_type": frame["Type"].astype(str).str.strip().str.lower(),
            "source_id": _clean_identifier(frame["Source"]),
            "transaction_date": _dates(frame["Created (UTC)"]),
            "available_date": _dates(frame["Available On (UTC)"]),
            "gross_amount": _money(frame["Amount"]),
            "processor_fee": _money(frame["Fee"]),
            "net_amount": _money(frame["Net"]),
            "reservation_id": _clean_identifier(
                frame.get(
                    "reservationId (metadata)",
                    pd.Series("", index=frame.index),
                )
            ),
            "channel_reservation_id": _clean_identifier(
                frame.get(
                    "confirmationCode (metadata)",
                    pd.Series("", index=frame.index),
                )
            ),
            "guest": frame.get(
                "guestName (metadata)",
                pd.Series("", index=frame.index),
            ).astype(str).str.strip(),
            "listing": frame.get(
                "listingNickname (metadata)",
                pd.Series("", index=frame.index),
            ).astype(str).str.strip(),
            "details": "",
            "source_file": path.name,
        }
    )

    duplicate_ids = output.loc[
        output["transaction_id"].ne("")
        & output["transaction_id"].duplicated(keep=False),
        "transaction_id",
    ].unique()

    if len(duplicate_ids):
        raise ValueError(
            f"{account_name} contains duplicate transaction IDs: "
            + ", ".join(duplicate_ids[:10])
        )

    return output


def normalize_airbnb(path: Path) -> pd.DataFrame:
    frame = _read_table(path)

    required = {
        "Date",
        "Type",
        "Confirmation code",
        "Guest",
        "Listing",
        "Details",
        "Reference code",
        "Amount",
        "Paid out",
        "Service fee",
        "Fast pay fee",
        "Gross earnings",
        "Airbnb remitted tax",
    }

    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Airbnb export missing columns: {missing}")

    transaction_type = frame["Type"].astype(str).str.strip().str.lower()
    reservation_rows = transaction_type.eq("reservation")

    transaction_id = _clean_identifier(frame["Reference code"])
    confirmation_code = _clean_identifier(frame["Confirmation code"])

    transaction_id = transaction_id.where(
        transaction_id.ne(""),
        confirmation_code,
    )

    payout_rows = transaction_type.eq("payout")

    # Airbnb detail rows use different monetary columns by row type:
    # reservations: Gross earnings less service fees equals Amount;
    # payouts: Paid out is the transfer amount;
    # adjustments/cancellation fees: Paid out and Gross earnings may be
    # blank or zero even though Amount and fees carry the payout effect.
    service_fee = (
        _money(frame["Service fee"])
        + _money(frame["Fast pay fee"])
    )

    non_payout_amount = _money(frame["Amount"])
    net_amount = non_payout_amount.where(
        ~payout_rows,
        _money(frame["Paid out"]),
    )

    non_payout_gross = _money(frame["Gross earnings"])

    # For non-reservation source events, derive gross when Airbnb leaves
    # Gross earnings at zero:
    #
    #     gross amount - processor fee = net amount
    #     gross amount = net amount + processor fee
    #
    # Examples:
    #   cancellation fee: -50.00 + 0.00 = -50.00 gross
    #   adjustment:       -65.57 + 12.03 = -53.54 gross
    source_event_rows = ~reservation_rows & ~payout_rows
    derived_source_event_gross = (
        net_amount + service_fee
    ).round(2)

    non_payout_gross = non_payout_gross.where(
        ~(
            source_event_rows
            & non_payout_gross.abs().le(0.005)
            & net_amount.abs().gt(0.005)
        ),
        derived_source_event_gross,
    )

    gross_amount = non_payout_gross.where(
        ~payout_rows,
        _money(frame["Paid out"]),
    )

    output = pd.DataFrame(
        {
            "processor": "Airbnb",
            "processor_account": "Airbnb",
            "transaction_id": transaction_id,
            "transaction_type": transaction_type,
            "source_id": _clean_identifier(frame["Reference code"]),
            "transaction_date": _dates(frame["Date"]),
            "available_date": _dates(frame["Arriving by date"]),
            "gross_amount": gross_amount,
            "processor_fee": service_fee,
            "net_amount": net_amount,
            "reservation_id": "",
            "channel_reservation_id": confirmation_code,
            "guest": frame["Guest"].astype(str).str.strip(),
            "listing": frame["Listing"].astype(str).str.strip(),
            "details": frame["Details"].astype(str).str.strip(),
            "airbnb_remitted_tax": _money(frame["Airbnb remitted tax"]),
            "source_file": path.name,
        }
    )

    return output


def normalize_bank(path: Path) -> pd.DataFrame:
    frame = _read_table(path)

    required = {
        "Account ID",
        "Transaction ID",
        "Date",
        "Description",
        "Amount",
        "Balance",
    }

    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Bank export missing columns: {missing}")

    description = frame["Description"].astype(str).str.strip()
    upper_description = description.str.upper()

    processor = pd.Series("", index=frame.index)
    processor = processor.mask(
        upper_description.str.contains("STRIPE", na=False),
        "Stripe",
    )
    processor = processor.mask(
        upper_description.str.contains("AIRBNB", na=False),
        "Airbnb",
    )

    output = pd.DataFrame(
        {
            "account_id": _clean_identifier(frame["Account ID"]),
            "transaction_id": _clean_identifier(frame["Transaction ID"]),
            "transaction_date": _dates(frame["Date"]),
            "description": description,
            "amount": _money(frame["Amount"]),
            "balance": _money(frame["Balance"]),
            "identified_processor": processor,
            "source_file": path.name,
        }
    )

    duplicate_ids = output.loc[
        output["transaction_id"].ne("")
        & output["transaction_id"].duplicated(keep=False),
        "transaction_id",
    ].unique()

    if len(duplicate_ids):
        raise ValueError(
            "Bank contains duplicate transaction IDs: "
            + ", ".join(duplicate_ids[:10])
        )

    return output


def normalize_quickbooks_inventory(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for path in paths:
        frame = _read_table(path)

        rows.append(
            {
                "file_name": path.name,
                "file_type": path.suffix.lower(),
                "row_count": len(frame),
                "column_count": len(frame.columns),
                "columns": " | ".join(str(column) for column in frame.columns),
                "modified_timestamp": pd.Timestamp(
                    path.stat().st_mtime,
                    unit="s",
                ),
            }
        )

    return pd.DataFrame(rows).sort_values(
        "file_name"
    ).reset_index(drop=True)