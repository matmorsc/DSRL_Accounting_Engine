from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


HISTORY_COLUMNS = [
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

SYNTHETIC_PREFIX = "AIRBNB-PAYOUT-"
TOLERANCE = 0.02

ECONOMIC_KEY = [
    "payment_event_id",
    "transaction_type",
    "reservation_id",
    "channel_reservation_id",
    "account",
    "class",
    "description",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate active Airbnb posting history from obsolete synthetic "
            "payout IDs to the authoritative payout IDs in the current ledger."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Repository root. Defaults to the directory containing this script.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the validated preview to config/posting_history.csv.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def money(value: object) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def economic_mask(
    frame: pd.DataFrame,
    row: pd.Series,
    *,
    payout_id: str,
) -> pd.Series:
    mask = frame["payout_id"].astype(str).str.strip().eq(payout_id)
    for column in ECONOMIC_KEY:
        mask &= (
            frame[column].astype(str).str.strip()
            == str(row.get(column, "")).strip()
        )
    mask &= (
        pd.to_numeric(frame["signed_amount"], errors="coerce")
        .fillna(0.0)
        .round(2)
        .eq(money(row.get("signed_amount")))
    )
    return mask


def validate_columns(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    config_dir = root / "config"
    processed_dir = root / "data" / "processed"
    output_dir = root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    history_path = config_dir / "posting_history.csv"
    proposed_path = processed_dir / "posting_history_proposed.csv"
    payments_path = processed_dir / "payment_ledger_v6.csv"
    payouts_path = processed_dir / "payout_ledger_v6.csv"

    try:
        history = read_csv(history_path)
        proposed = read_csv(proposed_path)
        payments = read_csv(payments_path)
        payouts = read_csv(payouts_path)

        validate_columns(history, HISTORY_COLUMNS, "Posting history")
        validate_columns(proposed, HISTORY_COLUMNS, "Proposed posting history")
        validate_columns(
            payments,
            ["payment_event_id", "transaction_type", "payout_id", "processor"],
            "Payment ledger",
        )
        validate_columns(
            payouts,
            [
                "payout_id",
                "processor",
                "payout_amount",
                "bank_amount",
                "bank_match_status",
            ],
            "Payout ledger",
        )

        synthetic = history.loc[
            history["processor"].eq("Airbnb")
            & history["status"].str.lower().eq("active")
            & history["payout_id"].str.startswith(SYNTHETIC_PREFIX, na=False)
        ].copy()

        if synthetic.empty:
            raise ValueError("No active synthetic Airbnb payout history was found.")

        diagnostics: list[dict[str, object]] = []
        additions: list[pd.Series] = []
        affected_real_payouts: set[str] = set()

        for _, old_row in synthetic.iterrows():
            event_id = str(old_row["payment_event_id"]).strip()
            transaction_type = str(old_row["transaction_type"]).strip().lower()

            current_events = payments.loc[
                payments["processor"].eq("Airbnb")
                & payments["payment_event_id"].eq(event_id)
                & payments["transaction_type"].str.strip().str.lower().eq(
                    transaction_type
                )
                & payments["payout_id"].astype(str).str.strip().ne("")
            ].copy()

            real_payouts = sorted(
                set(current_events["payout_id"].astype(str).str.strip())
            )
            if len(real_payouts) != 1:
                raise ValueError(
                    f"{event_id} / {transaction_type} maps to "
                    f"{len(real_payouts)} current payout IDs: {real_payouts}"
                )

            real_payout_id = real_payouts[0]
            if real_payout_id.startswith(SYNTHETIC_PREFIX):
                raise ValueError(
                    f"{event_id} still maps to synthetic payout {real_payout_id}."
                )
            affected_real_payouts.add(real_payout_id)

            existing_match = history.loc[
                economic_mask(history, old_row, payout_id=real_payout_id)
                & history["status"].str.lower().eq("active")
            ].copy()

            if len(existing_match) == 1:
                action = "Retire synthetic; equivalent real-ID line already active"
                replacement_line_id = existing_match.iloc[0]["posting_line_id"]
            elif len(existing_match) > 1:
                raise ValueError(
                    f"Multiple active real-ID matches for {old_row['posting_line_id']}."
                )
            else:
                proposed_match = proposed.loc[
                    economic_mask(proposed, old_row, payout_id=real_payout_id)
                ].copy()
                if len(proposed_match) != 1:
                    raise ValueError(
                        f"Expected one proposed replacement for "
                        f"{old_row['posting_line_id']}; found {len(proposed_match)}."
                    )

                replacement = proposed_match.iloc[0].copy()
                replacement["posting_type"] = old_row["posting_type"]
                replacement["status"] = "Active"
                replacement["classification_source"] = (
                    "Airbnb synthetic payout ID migration"
                )
                replacement["notes"] = (
                    f"Migrated from {old_row['payout_id']} / "
                    f"{old_row['posting_line_id']}"
                )
                additions.append(replacement)
                action = "Retire synthetic; activate proposed real-ID replacement"
                replacement_line_id = replacement["posting_line_id"]

            diagnostics.append(
                {
                    "old_payout_id": old_row["payout_id"],
                    "real_payout_id": real_payout_id,
                    "payment_event_id": event_id,
                    "transaction_type": transaction_type,
                    "account": old_row["account"],
                    "signed_amount": money(old_row["signed_amount"]),
                    "old_posting_line_id": old_row["posting_line_id"],
                    "replacement_posting_line_id": replacement_line_id,
                    "action": action,
                }
            )

        corrected = history.loc[
            ~history["posting_line_id"].isin(set(synthetic["posting_line_id"]))
        ].copy()
        if additions:
            corrected = pd.concat(
                [corrected, pd.DataFrame(additions)[HISTORY_COLUMNS]],
                ignore_index=True,
            )

        corrected = corrected[HISTORY_COLUMNS].copy()

        duplicate_line_ids = corrected.loc[
            corrected["posting_line_id"].duplicated(keep=False), "posting_line_id"
        ].unique()
        if len(duplicate_line_ids):
            raise ValueError(
                "Duplicate posting-line IDs after migration: "
                + ", ".join(duplicate_line_ids)
            )

        remaining_synthetic = corrected.loc[
            corrected["processor"].eq("Airbnb")
            & corrected["status"].str.lower().eq("active")
            & corrected["payout_id"].str.startswith(SYNTHETIC_PREFIX, na=False)
        ]
        if not remaining_synthetic.empty:
            raise ValueError(
                f"{len(remaining_synthetic)} active synthetic lines remain."
            )

        active = corrected.loc[corrected["status"].str.lower().eq("active")].copy()
        active["signed_amount_number"] = pd.to_numeric(
            active["signed_amount"], errors="coerce"
        ).fillna(0.0)

        payout_checks: list[dict[str, object]] = []
        for payout_id in sorted(affected_real_payouts):
            payout_rows = payouts.loc[payouts["payout_id"].eq(payout_id)]
            if len(payout_rows) != 1:
                raise ValueError(
                    f"Expected one payout-ledger row for {payout_id}; "
                    f"found {len(payout_rows)}."
                )
            payout_row = payout_rows.iloc[0]
            history_total = round(
                active.loc[
                    active["payout_id"].eq(payout_id), "signed_amount_number"
                ].sum(),
                2,
            )
            payout_amount = money(payout_row["payout_amount"])
            bank_amount = money(payout_row["bank_amount"])
            difference = round(history_total - payout_amount, 2)
            bank_difference = round(bank_amount - payout_amount, 2)

            if abs(difference) > TOLERANCE:
                raise ValueError(
                    f"Corrected history for {payout_id} differs from payout by "
                    f"{difference:.2f}."
                )
            if abs(bank_difference) > TOLERANCE:
                raise ValueError(
                    f"Bank amount for {payout_id} differs from payout by "
                    f"{bank_difference:.2f}."
                )
            if str(payout_row["bank_match_status"]).strip() != "Matched":
                raise ValueError(f"{payout_id} is not bank-matched.")

            payout_checks.append(
                {
                    "payout_id": payout_id,
                    "history_total": history_total,
                    "payout_amount": payout_amount,
                    "bank_amount": bank_amount,
                    "difference": difference,
                    "bank_match_status": payout_row["bank_match_status"],
                    "status": "PASS",
                }
            )

        preview_path = output_dir / "posting_history_airbnb_migration_preview.csv"
        diagnostics_path = output_dir / "airbnb_payout_history_migration_diagnostics.csv"
        checks_path = output_dir / "airbnb_payout_history_migration_checks.csv"

        corrected.to_csv(preview_path, index=False)
        pd.DataFrame(diagnostics).to_csv(diagnostics_path, index=False)
        pd.DataFrame(payout_checks).to_csv(checks_path, index=False)

        print("DSRL Airbnb Payout-History Migration")
        print("=" * 52)
        print(f"Current history lines:       {len(history):>6}")
        print(f"Synthetic lines retired:     {len(synthetic):>6}")
        print(f"Real-ID lines activated:     {len(additions):>6}")
        print(f"Corrected history lines:     {len(corrected):>6}")
        print(f"Affected payouts:            {len(payout_checks):>6}")
        print()
        print("Affected payout checks")
        print("-" * 52)
        print(pd.DataFrame(payout_checks).to_string(index=False))
        print()
        print(f"Preview:     {preview_path}")
        print(f"Diagnostics: {diagnostics_path}")
        print(f"Checks:      {checks_path}")

        if not args.apply:
            print()
            print("PREVIEW ONLY. posting_history.csv was not modified.")
            print("Rerun with --apply only after reviewing the checks.")
            return 0

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = output_dir / f"posting_history_before_airbnb_migration_{timestamp}.csv"
        shutil.copy2(history_path, backup_path)

        temp_path = history_path.with_suffix(".csv.tmp")
        corrected.to_csv(temp_path, index=False)
        os.replace(temp_path, history_path)

        print()
        print(f"Backup: {backup_path}")
        print(f"UPDATED: {history_path}")
        print("No QuickBooks transactions were created.")
        return 0

    except Exception as exc:
        print(f"ERROR: Airbnb payout-history migration failed: {exc}")
        print("posting_history.csv was not modified.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
