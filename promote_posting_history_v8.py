from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.posting.history import (
    read_posting_history,
)
from src.posting.history_promotion import (
    promote_approved_posting_history,
    write_posting_history_atomic,
)


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
HISTORY_PATH = ROOT / "config" / "posting_history.csv"


def read_csv(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}."
        )
    return pd.read_csv(path)


def main() -> int:
    print("DSRL Posting History V8 - Phase B Promotion")
    print("=" * 48)

    try:
        proposed = read_csv(
            "posting_history_proposed.csv"
        )
        review = read_csv(
            "posting_history_review.csv"
        )
        existing = read_posting_history(
            HISTORY_PATH
        )

        approved_events = (
            review["approved_for_promotion"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("yes")
            .sum()
        )

        if approved_events == 0:
            raise ValueError(
                "No review rows are marked "
                "approved_for_promotion=Yes."
            )

        combined, diagnostics = (
            promote_approved_posting_history(
                proposed_history=proposed,
                review=review,
                existing_history=existing,
            )
        )

        promoted_lines = len(combined) - len(existing)

        preview_path = (
            PROCESSED
            / "posting_history_promotion_preview.csv"
        )
        diagnostics_path = (
            PROCESSED
            / "posting_history_promotion_diagnostics.csv"
        )

        combined.to_csv(
            preview_path,
            index=False,
        )
        diagnostics.to_csv(
            diagnostics_path,
            index=False,
        )

        print(f"Approved payment events:   {approved_events:>6}")
        print(f"Existing history lines:    {len(existing):>6}")
        print(f"New lines to promote:      {promoted_lines:>6}")
        print(f"Resulting history lines:   {len(combined):>6}")
        print()
        print(f"Preview: {preview_path}")
        print()

        confirm = input(
            "Type PROMOTE to replace config/posting_history.csv: "
        ).strip()

        if confirm != "PROMOTE":
            print(
                "Promotion cancelled. Preview was preserved."
            )
            return 0

        write_posting_history_atomic(
            combined,
            HISTORY_PATH,
        )

    except Exception as exc:
        print(
            f"ERROR: Posting history promotion failed: "
            f"{exc}"
        )
        return 1

    print()
    print(
        f"Posting history updated: {HISTORY_PATH}"
    )
    print("No QuickBooks transactions were created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
