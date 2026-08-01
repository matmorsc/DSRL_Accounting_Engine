from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "account_id",
    "account_name",
    "automatic_payout_id",
    "automatic_payout_effective_at",
    "balance_transaction_id",
    "created",
    "available_on",
    "currency",
    "gross",
    "fee",
    "net",
    "reporting_category",
    "description",
}


def discover_payout_reconciliation_files(
    root: Path,
) -> list[Path]:
    folder = (
        root
        / "data"
        / "raw"
        / "stripe"
        / "payout_reconciliation"
    )

    if not folder.exists():
        return []

    return sorted(
        path
        for path in folder.rglob("*.csv")
        if path.is_file()
    )


def normalize_payout_reconciliation(
    paths: list[Path],
    *,
    account_mapping: dict[str, str],
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    for path in paths:
        frame = pd.read_csv(path)

        missing = sorted(
            REQUIRED_COLUMNS.difference(frame.columns)
        )
        if missing:
            raise ValueError(
                f"{path.name} missing columns: {missing}"
            )

        normalized = pd.DataFrame(
            {
                "stripe_account_id": (
                    frame["account_id"]
                    .astype(str)
                    .str.strip()
                ),
                "stripe_account_name": (
                    frame["account_name"]
                    .astype(str)
                    .str.strip()
                ),
                "processor_account": (
                    frame["account_name"]
                    .astype(str)
                    .str.strip()
                    .map(account_mapping)
                    .fillna("")
                ),
                "payout_id": (
                    frame["automatic_payout_id"]
                    .astype(str)
                    .str.strip()
                ),
                "payout_effective_at": pd.to_datetime(
                    frame["automatic_payout_effective_at"],
                    errors="coerce",
                ),
                "balance_transaction_id": (
                    frame["balance_transaction_id"]
                    .astype(str)
                    .str.strip()
                ),
                "transaction_created_at": pd.to_datetime(
                    frame["created"],
                    errors="coerce",
                ),
                "available_on": pd.to_datetime(
                    frame["available_on"],
                    errors="coerce",
                ),
                "currency": (
                    frame["currency"]
                    .astype(str)
                    .str.lower()
                    .str.strip()
                ),
                "gross": pd.to_numeric(
                    frame["gross"],
                    errors="coerce",
                ).fillna(0.0),
                "fee": pd.to_numeric(
                    frame["fee"],
                    errors="coerce",
                ).fillna(0.0),
                "net": pd.to_numeric(
                    frame["net"],
                    errors="coerce",
                ).fillna(0.0),
                "reporting_category": (
                    frame["reporting_category"]
                    .astype(str)
                    .str.lower()
                    .str.strip()
                ),
                "description": (
                    frame["description"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                ),
                "source_file": path.name,
            }
        )

        frames.append(normalized)

    columns = [
        "stripe_account_id",
        "stripe_account_name",
        "processor_account",
        "payout_id",
        "payout_effective_at",
        "balance_transaction_id",
        "transaction_created_at",
        "available_on",
        "currency",
        "gross",
        "fee",
        "net",
        "reporting_category",
        "description",
        "source_file",
    ]

    if not frames:
        return pd.DataFrame(columns=columns)

    output = pd.concat(
        frames,
        ignore_index=True,
    )

    output = output.loc[
        output["payout_id"].ne("")
        & output["balance_transaction_id"].ne("")
    ].copy()

    duplicate_keys = (
        output.groupby(
            [
                "processor_account",
                "balance_transaction_id",
            ],
            dropna=False,
        )["payout_id"]
        .nunique()
    )
    conflicts = duplicate_keys.loc[
        duplicate_keys.gt(1)
    ]

    if not conflicts.empty:
        conflict_ids = ", ".join(
            key[1] for key in conflicts.index
        )
        raise ValueError(
            "Balance transactions assigned to multiple payouts: "
            + conflict_ids
        )

    output = output.drop_duplicates(
        subset=[
            "processor_account",
            "balance_transaction_id",
            "payout_id",
        ],
        keep="last",
    )

    for column in ["gross", "fee", "net"]:
        output[column] = output[column].round(2)

    return output[columns].sort_values(
        [
            "processor_account",
            "payout_effective_at",
            "balance_transaction_id",
        ]
    ).reset_index(drop=True)
