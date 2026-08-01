from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.posting.airbnb_adjustments import (
    promote_airbnb_adjustments,
)
from src.posting.history import (
    read_posting_history,
)
from src.posting.history_promotion import (
    write_posting_history_atomic,
)


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
HISTORY_PATH = ROOT / "config" / "posting_history.csv"


def read_processed(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}.")
    return pd.read_csv(path)


def main() -> int:
    print("DSRL Airbnb Adjustment Promotion")
    print("=" * 42)

    try:
        proposed = read_processed(
            "posting_history_proposed.csv"
        )
        review = read_processed(
            "airbnb_adjustment_review.csv"
        )
        existing = read_posting_history(
            HISTORY_PATH
        )

        approved = (
            review["approved_for_promotion"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("yes")
            .sum()
        )

        if approved == 0:
            raise ValueError(
                "No adjustment rows are approved."
            )

        combined, diagnostics = (
            promote_airbnb_adjustments(
                proposed_history=proposed,
                review=review,
                existing_history=existing,
            )
        )

        new_lines = len(combined) - len(existing)

        preview_path = (
            PROCESSED
            / "airbnb_adjustment_promotion_preview.csv"
        )
        diagnostics_path = (
            PROCESSED
            / "airbnb_adjustment_promotion_diagnostics.csv"
        )

        combined.to_csv(
            preview_path,
            index=False,
        )
        diagnostics.to_csv(
            diagnostics_path,
            index=False,
        )

        print(f"Approved groups:        {approved:>6}")
        print(f"Existing history lines: {len(existing):>6}")
        print(f"New adjustment lines:   {new_lines:>6}")
        print(f"Resulting history lines:{len(combined):>6}")
        print()
        print(f"Preview: {preview_path}")
        print()

        confirm = input(
            "Type PROMOTE to update posting history: "
        ).strip()

        if confirm != "PROMOTE":
            print(
                "Promotion cancelled. Preview preserved."
            )
            return 0

        write_posting_history_atomic(
            combined,
            HISTORY_PATH,
        )

    except Exception as exc:
        print(
            f"ERROR: Airbnb adjustment promotion failed: {exc}"
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
