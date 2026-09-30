from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


SEED_COLUMNS = [
    "posting_line_id",
    "posting_group_id",
    "payment_event_id",
    "processor",
    "processor_account",
    "transaction_id",
    "transaction_type",
    "transaction_date",
    "source_id",
    "payout_id",
    "reservation_id",
    "channel_reservation_id",
    "guest",
    "listing",
    "account",
    "class",
    "description",
    "signed_amount",
    "posting_type",
    "reversal_of_posting_line_id",
    "classification_source",
    "created_by",
    "created_at",
    "status",
    "notes",
]

STRIPE_PAYOUT = "po_1U09ljJtejknM735wEs1jEcW"
AIRBNB_PAYOUT = "G-CCJXTCZZ4PVDE"


def stable_id(prefix: str, *parts: str) -> str:
    payload = "|".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"


def money(value: object) -> Decimal:
    try:
        return Decimal(str(value or "0").strip()).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid monetary value: {value!r}") from exc


def read_rows(path: Path, required: bool = True) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Missing required file: {path}")
        return [], []

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        return columns, [dict(row) for row in reader]


def correction_rows(created_at: str) -> list[dict[str, str]]:
    stripe_event = "Main Guesty::txn_1Tz6NbJtejknM735cd6fytoD"
    stripe_group = stable_id("pg", STRIPE_PAYOUT, stripe_event)
    stripe_line = stable_id(
        "pl",
        STRIPE_PAYOUT,
        stripe_event,
        "Bank Charges & Fees:Stripe Processing Fees",
        "-15.00",
    )

    airbnb_event = "Airbnb::HMASHPNYMH::pet_fee_20260807"
    airbnb_group = stable_id("pg", AIRBNB_PAYOUT, airbnb_event)
    airbnb_line = stable_id(
        "pl",
        AIRBNB_PAYOUT,
        airbnb_event,
        "Motel Rent - Short Term",
        "50.00",
    )

    blank = {column: "" for column in SEED_COLUMNS}

    stripe = {
        **blank,
        "posting_line_id": stripe_line,
        "posting_group_id": stripe_group,
        "payment_event_id": stripe_event,
        "processor": "Stripe",
        "processor_account": "Main Guesty",
        "transaction_id": "txn_1Tz6NbJtejknM735cd6fytoD",
        "transaction_type": "adjustment",
        "transaction_date": "2026-07-31 02:40:58",
        "source_id": "txn_1Tz6NbJtejknM735cd6fytoD",
        "payout_id": STRIPE_PAYOUT,
        "account": "Bank Charges & Fees:Stripe Processing Fees",
        "class": "Hospitality",
        "description": "Stripe card dispute countered fee",
        "signed_amount": "-15.00",
        "posting_type": "Source Event",
        "classification_source": "Stripe payout reconciliation",
        "created_by": "DSRL current payout correction",
        "created_at": created_at,
        "status": "Active",
        "notes": (
            "Evidence: Stripe itemized payout reconciliation; balance transaction "
            "txn_1Tz6NbJtejknM735cd6fytoD; reporting category fee; description "
            "Card Dispute Countered Fee (2026-07-13); net -15.00."
        ),
    }

    airbnb = {
        **blank,
        "posting_line_id": airbnb_line,
        "posting_group_id": airbnb_group,
        "payment_event_id": airbnb_event,
        "processor": "Airbnb",
        "processor_account": "Airbnb",
        "transaction_id": "G-CCJXTCZZ4PVDE::pet_fee",
        "transaction_type": "adjustment",
        "transaction_date": "2026-08-07 00:00:00",
        "source_id": "G-CCJXTCZZ4PVDE",
        "payout_id": AIRBNB_PAYOUT,
        "reservation_id": "6a6cf33452645a1ddee93f3c",
        "channel_reservation_id": "HMASHPNYMH",
        "guest": "Krista Munoz",
        "listing": "DSRL Lodge Room 6",
        "account": "Motel Rent - Short Term",
        "class": "Hospitality",
        "description": "Pet fee - DSRL Lodge Room 6",
        "signed_amount": "50.00",
        "posting_type": "Source Event",
        "classification_source": "Airbnb pet fee evidence",
        "created_by": "DSRL current payout correction",
        "created_at": created_at,
        "status": "Active",
        "notes": (
            "Evidence: Airbnb payout G-CCJXTCZZ4PVDE deposited 50.00 on 2026-08-07; "
            "owner identified it as Krista Munoz's pet fee; Guesty reservation "
            "6a6cf33452645a1ddee93f3c / HMASHPNYMH is DSRL Lodge Room 6. No Airbnb "
            "service fee or separately reported tax applied to this payout."
        ),
    }

    return [stripe, airbnb]


def is_active(row: dict[str, str]) -> bool:
    return str(row.get("status", "")).strip().lower() == "active"


def is_proposed_reversal(row: dict[str, str]) -> bool:
    return (
        str(row.get("status", "")).strip().lower() == "proposed"
        and str(row.get("posting_type", "")).strip() == "Reversal"
    )


def payout_total(rows: list[dict[str, str]], payout_id: str) -> Decimal:
    return sum(
        (money(row.get("signed_amount")) for row in rows if row.get("payout_id", "").strip() == payout_id),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))


def write_atomic(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=path.parent,
        prefix=f".{path.stem}_",
        suffix=".tmp",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add the verified Stripe dispute fee and Airbnb pet-fee posting seeds."
    )
    parser.add_argument("--apply", action="store_true", help="Back up and update the manual seed file.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="DSRL Accounting Engine root (defaults to the script directory).",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    seed_path = root / "config" / "posting_history_manual_seeds.csv"
    history_path = root / "config" / "posting_history.csv"
    reversal_path = root / "data" / "processed" / "posting_history_reversal_preview.csv"

    try:
        seed_columns, seeds = read_rows(seed_path)
        if seed_columns != SEED_COLUMNS:
            raise ValueError(
                "Manual seed columns do not match the expected posting-history schema.\n"
                f"Expected: {SEED_COLUMNS}\nFound: {seed_columns}"
            )

        _, history = read_rows(history_path)
        _, reversals = read_rows(reversal_path)

        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        candidates = correction_rows(created_at)

        existing_ids = {row.get("posting_line_id", "").strip() for row in seeds + history + reversals}
        additions: list[dict[str, str]] = []
        already_present: list[dict[str, str]] = []

        for candidate in candidates:
            semantic_matches = [
                row
                for row in seeds
                if row.get("payout_id", "").strip() == candidate["payout_id"]
                and row.get("account", "").strip() == candidate["account"]
                and money(row.get("signed_amount")) == money(candidate["signed_amount"])
                and is_active(row)
            ]
            if semantic_matches:
                match = semantic_matches[0]
                if match.get("posting_line_id", "").strip() != candidate["posting_line_id"]:
                    print(
                        "NOTICE: Equivalent active correction already exists with posting_line_id "
                        f"{match.get('posting_line_id', '')}."
                    )
                already_present.append(candidate)
                continue

            if candidate["posting_line_id"] in existing_ids:
                raise ValueError(
                    f"Posting line ID collision for {candidate['posting_line_id']}; no file was changed."
                )
            additions.append(candidate)
            existing_ids.add(candidate["posting_line_id"])

        simulated_seeds = seeds + additions
        active_ledger = (
            [row for row in history if is_active(row)]
            + [row for row in simulated_seeds if is_active(row)]
            + [row for row in reversals if is_proposed_reversal(row)]
        )

        expected = {
            STRIPE_PAYOUT: Decimal("569.07"),
            AIRBNB_PAYOUT: Decimal("50.00"),
        }
        actual = {payout_id: payout_total(active_ledger, payout_id) for payout_id in expected}

        print("DSRL Current Payout Corrections")
        print("=" * 48)
        print(f"Manual seed file:       {seed_path}")
        print(f"Existing seed lines:    {len(seeds):>6}")
        print(f"Lines already present:  {len(already_present):>6}")
        print(f"Lines to add:           {len(additions):>6}")
        print()
        print("Correction lines")
        print("-" * 48)
        for row in candidates:
            state = "Already present" if row in already_present else "Will add"
            print(
                f"{state:<15} {row['payout_id']:<28} "
                f"{row['signed_amount']:>8}  {row['description']}"
            )

        print()
        print("Simulated ledger validation")
        print("-" * 48)
        for payout_id, expected_total in expected.items():
            total = actual[payout_id]
            status = "PASS" if total == expected_total else "FAIL"
            print(
                f"{payout_id:<28} actual {total:>9}  expected {expected_total:>9}  {status}"
            )

        failures = [payout_id for payout_id in expected if actual[payout_id] != expected[payout_id]]
        if failures:
            raise ValueError(
                "Simulated ledger validation failed for: " + ", ".join(failures)
            )

        if not args.apply:
            print()
            print("Preview only. Run again with --apply to update the manual seed file.")
            return 0

        if not additions:
            print()
            print("No update needed; both correction lines are already active.")
            return 0

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = seed_path.with_name(f"{seed_path.stem}_before_current_corrections_{stamp}.csv")
        shutil.copy2(seed_path, backup)
        write_atomic(seed_path, seed_columns, simulated_seeds)

        print()
        print(f"Backup created:         {backup}")
        print(f"Manual seeds updated:   {seed_path}")
        print(f"Resulting seed lines:   {len(simulated_seeds):>6}")
        print("No QuickBooks transactions were created.")
        return 0

    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
