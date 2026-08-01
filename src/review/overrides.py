from __future__ import annotations

from pathlib import Path

import pandas as pd


PAYMENT_MATCH_COLUMNS = [
    "payment_event_id",
    "reservation_id",
    "channel_reservation_id",
    "status",
    "notes",
]

PAYOUT_ADJUSTMENT_COLUMNS = [
    "payout_id",
    "adjustment_type",
    "amount",
    "account",
    "class",
    "description",
    "status",
    "notes",
]


def _read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)

    frame = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
    )

    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(
            f"{path.name} missing columns: {missing}"
        )

    return frame[columns].copy()


def read_manual_payment_matches(path: Path) -> pd.DataFrame:
    frame = _read_csv(path, PAYMENT_MATCH_COLUMNS)

    if frame.empty:
        return frame

    return frame.loc[
        frame["status"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"accepted", "active"})
    ].copy()


def read_payout_adjustments(path: Path) -> pd.DataFrame:
    frame = _read_csv(path, PAYOUT_ADJUSTMENT_COLUMNS)

    if frame.empty:
        return frame

    active = frame.loc[
        frame["status"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"accepted", "active"})
    ].copy()

    active["amount"] = pd.to_numeric(
        active["amount"],
        errors="coerce",
    ).fillna(0.0)

    return active


def apply_manual_payment_matches(
    payment_ledger: pd.DataFrame,
    matches: pd.DataFrame,
) -> pd.DataFrame:
    output = payment_ledger.copy()

    if matches.empty:
        output["manual_match_applied"] = "No"
        return output

    duplicate_ids = (
        matches["payment_event_id"]
        .astype(str)
        .str.strip()
        .value_counts()
    )
    duplicate_ids = duplicate_ids.loc[
        duplicate_ids.gt(1)
    ].index.tolist()

    if duplicate_ids:
        raise ValueError(
            "Multiple active manual payment matches found for: "
            + ", ".join(duplicate_ids)
        )

    lookup = {
        str(row["payment_event_id"]).strip(): row
        for _, row in matches.iterrows()
        if str(row["payment_event_id"]).strip()
    }

    output["manual_match_applied"] = "No"

    for idx, event in output.iterrows():
        event_id = str(
            event.get("payment_event_id", "")
        ).strip()

        override = lookup.get(event_id)
        if override is None:
            continue

        output.at[idx, "reservation_id"] = str(
            override.get("reservation_id", "")
        ).strip()
        output.at[idx, "channel_reservation_id"] = str(
            override.get("channel_reservation_id", "")
        ).strip()
        output.at[idx, "manual_match_applied"] = "Yes"

    return output


def append_unique_row(
    path: Path,
    row: dict[str, object],
    columns: list[str],
    unique_columns: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_csv(path, columns)

    if not existing.empty:
        mask = pd.Series(True, index=existing.index)
        for column in unique_columns:
            mask &= (
                existing[column]
                .astype(str)
                .str.strip()
                .eq(str(row.get(column, "")).strip())
            )

        if mask.any():
            existing.loc[mask, columns] = [
                str(row.get(column, ""))
                for column in columns
            ]
            existing.to_csv(path, index=False)
            return

    updated = pd.concat(
        [
            existing,
            pd.DataFrame(
                [[row.get(column, "") for column in columns]],
                columns=columns,
            ),
        ],
        ignore_index=True,
    )
    updated.to_csv(path, index=False)
