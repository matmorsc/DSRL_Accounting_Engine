from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.posting.history import (
    POSTING_HISTORY_COLUMNS,
    validate_posting_history,
)


def test_seed_lines_balance_original_charge():
    path = (
        Path(__file__).resolve().parents[1]
        / "config"
        / "posting_history_manual_seeds.csv"
    )
    seeds = pd.read_csv(path)

    target = seeds.loc[
        seeds["source_id"].eq(
            "ch_3ToU7JJtejknM7351lfydf5x"
        )
    ]

    assert len(target) == 4
    assert round(
        pd.to_numeric(
            target["signed_amount"]
        ).sum(),
        2,
    ) == 105.19

    positive = target.loc[
        pd.to_numeric(
            target["signed_amount"]
        ).gt(0)
    ]
    negative = target.loc[
        pd.to_numeric(
            target["signed_amount"]
        ).lt(0)
    ]

    assert round(
        pd.to_numeric(
            positive["signed_amount"]
        ).sum(),
        2,
    ) == 109.09
    assert round(
        pd.to_numeric(
            negative["signed_amount"]
        ).sum(),
        2,
    ) == -3.90


def test_seed_ids_are_unique():
    path = (
        Path(__file__).resolve().parents[1]
        / "config"
        / "posting_history_manual_seeds.csv"
    )
    seeds = pd.read_csv(path)

    validate_posting_history(
        seeds[POSTING_HISTORY_COLUMNS]
    )
