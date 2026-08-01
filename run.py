from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "settings.yaml"
OUTPUT_DIR = ROOT / "output"

SOURCE_FOLDERS = {
    "Guesty": ROOT / "data" / "raw" / "guesty",
    "Stripe Main": ROOT / "data" / "raw" / "stripe" / "main",
    "Stripe Cognito": ROOT / "data" / "raw" / "stripe" / "cognito",
    "Stripe Keycheck": ROOT / "data" / "raw" / "stripe" / "keycheck",
    "Airbnb": ROOT / "data" / "raw" / "airbnb",
    "Bank": ROOT / "data" / "raw" / "bank",
    "QuickBooks": ROOT / "data" / "raw" / "quickbooks",
}

REQUIRED_COLUMNS = {
    "Guesty": {
        "GUEST",
        "LISTING'S NICKNAME",
        "CONFIRMATION DATE",
        "CHECK-IN",
        "CHECK-OUT",
        "SOURCE",
        "PAYMENT METHOD",
        "TOTAL PAID",
        "TOTAL REFUNDED",
        "CHANNEL RESERVATION ID",
        "RESERVATION ID",
    },
    "Stripe Main": {
        "id",
        "Type",
        "Source",
        "Amount",
        "Fee",
        "Net",
        "Created (UTC)",
        "Available On (UTC)",
    },
    "Stripe Cognito": {
        "id",
        "Type",
        "Source",
        "Amount",
        "Fee",
        "Net",
        "Created (UTC)",
        "Available On (UTC)",
    },
    "Stripe Keycheck": {
        "id",
        "Type",
        "Source",
        "Amount",
        "Fee",
        "Net",
        "Created (UTC)",
        "Available On (UTC)",
    },
    "Airbnb": {
        "Date",
        "Type",
        "Confirmation code",
        "Guest",
        "Listing",
        "Amount",
        "Paid out",
        "Gross earnings",
        "Airbnb remitted tax",
    },
    "Bank": {
        "Transaction ID",
        "Date",
        "Description",
        "Amount",
        "Balance",
    },
}


def newest_data_file(folder: Path) -> Path | None:
    candidates = [
        path
        for path in folder.iterdir()
        if path.is_file()
        and path.name.lower() != "readme.md"
        and path.suffix.lower() in {".csv", ".xlsx", ".xls"}
    ]

    if not candidates:
        return None

    return max(candidates, key=lambda path: path.stat().st_mtime)


def read_headers(path: Path) -> list[str]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            return next(reader)

    frame = pd.read_excel(path, nrows=0)
    return list(frame.columns)


def row_count(path: Path) -> int:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return max(sum(1 for _ in handle) - 1, 0)

    return len(pd.read_excel(path))


def validate_columns(source_name: str, headers: Iterable[str]) -> list[str]:
    required = REQUIRED_COLUMNS.get(source_name)

    if not required:
        return []

    header_set = set(headers)
    return sorted(required.difference(header_set))


def main() -> int:
    print("DSRL Accounting Engine")
    print("=" * 40)

    if not CONFIG_PATH.exists():
        print(f"ERROR: Missing configuration file:\n{CONFIG_PATH}")
        return 1

    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        settings = yaml.safe_load(handle)

    print(f"Business: {settings['business']['name']}")
    print()

    inventory_rows: list[dict[str, object]] = []
    errors: list[str] = []

    for source_name, folder in SOURCE_FOLDERS.items():
        if not folder.exists():
            errors.append(f"{source_name}: folder does not exist: {folder}")
            continue

        path = newest_data_file(folder)

        if path is None:
            errors.append(f"{source_name}: no data file found")
            continue

        try:
            headers = read_headers(path)
            count = row_count(path)
            missing = validate_columns(source_name, headers)

            status = "Valid" if not missing else "Missing columns"

            inventory_rows.append(
                {
                    "source": source_name,
                    "file": path.name,
                    "full_path": str(path),
                    "rows": count,
                    "modified": datetime.fromtimestamp(
                        path.stat().st_mtime
                    ).isoformat(timespec="seconds"),
                    "status": status,
                    "missing_columns": ", ".join(missing),
                }
            )

            print(f"{source_name:<18} {count:>6} rows  {path.name}")

            if missing:
                errors.append(
                    f"{source_name}: missing required columns: {', '.join(missing)}"
                )

        except Exception as exc:
            errors.append(f"{source_name}: could not read {path.name}: {exc}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output_path = OUTPUT_DIR / f"source_inventory_{timestamp}.csv"

    pd.DataFrame(inventory_rows).to_csv(output_path, index=False)

    print()
    print(f"Inventory saved to:\n{output_path}")

    if errors:
        print()
        print("VALIDATION ISSUES")
        print("-" * 40)

        for error in errors:
            print(f"- {error}")

        return 1

    print()
    print("Validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())