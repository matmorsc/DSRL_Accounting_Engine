from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

from src.posting.history import (
    POSTING_HISTORY_COLUMNS,
    read_posting_history,
)
from src.posting.ledger_deposit_drafts import (
    build_ledger_deposit_drafts,
    combine_ledger_sources,
    compare_deposit_drafts,
)


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
HISTORY = ROOT / "config" / "posting_history.csv"
SEEDS = (
    ROOT / "config"
    / "posting_history_manual_seeds.csv"
)
SETTINGS = ROOT / "config" / "settings.yaml"


def read_processed(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}.")
    return pd.read_csv(path)


def read_optional_history(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(
            columns=POSTING_HISTORY_COLUMNS
        )
    frame = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
    )
    return frame[POSTING_HISTORY_COLUMNS]


def choose_file(candidates: list[str], label: str) -> str:
    for name in candidates:
        if (PROCESSED / name).exists():
            return name
    raise FileNotFoundError(f"No {label} file found.")


def main() -> int:
    print("DSRL Ledger-Backed Deposit Drafts V9")
    print("=" * 48)

    try:
        with SETTINGS.open(
            "r",
            encoding="utf-8",
        ) as handle:
            settings = yaml.safe_load(handle)

        tolerance = float(
            settings["matching"]["amount_tolerance"]
        )

        legacy_file = choose_file(
            [
                "deposit_drafts_v6.csv",
                "deposit_drafts_v2.csv",
            ],
            "legacy deposit draft",
        )
        payout_file = choose_file(
            [
                "payout_ledger_v6.csv",
                "payout_ledger.csv",
            ],
            "payout ledger",
        )
        posting_status_file = choose_file(
            [
                "posting_status_v6.csv",
                "posting_status.csv",
            ],
            "posting status",
        )

        persistent = read_posting_history(HISTORY)
        seeds = read_optional_history(SEEDS)
        reversals = read_processed(
            "posting_history_reversal_preview.csv"
        )

        combined_all = combine_ledger_sources(
            persistent_history=persistent,
            manual_seeds=seeds,
            reversal_preview=reversals,
        )

        posting_status = read_processed(
            posting_status_file
        )
        eligible_payout_ids = set(
            posting_status.loc[
                posting_status["generate_entry"]
                .astype(str)
                .str.strip()
                .str.lower()
                .eq("yes"),
                "payout_id",
            ]
            .astype(str)
            .str.strip()
        )

        combined = combined_all.loc[
            combined_all["payout_id"]
            .astype(str)
            .str.strip()
            .isin(eligible_payout_ids)
        ].copy()

        drafts, lines = build_ledger_deposit_drafts(
            ledger_lines=combined,
            payout_ledger=read_processed(
                payout_file
            ),
            tolerance=tolerance,
        )

        comparison = compare_deposit_drafts(
            ledger_drafts=drafts,
            legacy_drafts=read_processed(
                legacy_file
            ),
        )

        outputs = {
            "ledger_lines_v9.csv": combined,
            "deposit_drafts_v9.csv": drafts,
            "deposit_draft_lines_v9.csv": lines,
            "deposit_draft_comparison_v9.csv": comparison,
        }

        for name, frame in outputs.items():
            frame.to_csv(
                PROCESSED / name,
                index=False,
            )

    except Exception as exc:
        print(
            f"ERROR: Ledger-backed deposits failed: "
            f"{exc}"
        )
        return 1

    print(f"Legacy draft source:        {legacy_file}")
    print(f"Payout ledger source:       {payout_file}")
    print(f"Posting status source:      {posting_status_file}")
    print(f"Eligible payout IDs:        {len(eligible_payout_ids):>6}")
    print(f"Persistent history lines:   {len(persistent):>6}")
    print(f"Manual seed lines:          {len(seeds):>6}")
    print(f"Reversal preview lines:     {len(reversals):>6}")
    print(f"All ledger lines w/payout:  {len(combined_all):>6}")
    print(f"Eligible ledger lines:      {len(combined):>6}")
    print(f"Ledger deposit drafts:      {len(drafts):>6}")
    print(f"Ledger deposit lines:       {len(lines):>6}")
    print()

    print("Ledger balance check")
    print("-" * 48)
    print(
        drafts["balanced"]
        .value_counts(dropna=False)
        .sort_index()
        .to_string()
    )
    print()

    print("V9 vs legacy")
    print("-" * 48)
    print(
        comparison["comparison_status"]
        .value_counts(dropna=False)
        .sort_index()
        .to_string()
    )

    worse = comparison.loc[
        comparison["comparison_status"].eq("Worse")
    ]
    if not worse.empty:
        print()
        print("Worse payouts requiring investigation")
        print("-" * 48)
        print(
            worse[
                [
                    "payout_id",
                    "processor",
                    "payout_amount",
                    "legacy_draft_total",
                    "legacy_difference",
                    "ledger_draft_total",
                    "ledger_difference",
                ]
            ].to_string(index=False)
        )

    target = "po_1TqjcpJtejknM735RBYtfOau"
    target_row = comparison.loc[
        comparison["payout_id"]
        .astype(str)
        .eq(target)
    ]

    print()
    print("Dan Calabro payout acceptance test")
    print("-" * 48)

    if target_row.empty:
        print("Target payout not found.")
    else:
        row = target_row.iloc[0]
        print(f"Payout amount:       {row['payout_amount']}")
        print(f"Legacy draft total:  {row['legacy_draft_total']}")
        print(f"Ledger draft total:  {row['ledger_draft_total']}")
        print(f"Ledger difference:   {row['ledger_difference']}")
        print(f"Ledger balanced:     {row['ledger_balanced']}")
        print(f"Comparison status:   {row['comparison_status']}")

    print()
    print("Primary deposit builder was not replaced.")
    print("Persistent posting history was not modified.")
    print("No QuickBooks transactions were created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
