from __future__ import annotations

import sys
from pathlib import Path

from src.presentation.posting_workbook import (
    export_posting_package,
    load_summary,
    output_filename,
)


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "output"


def main() -> int:
    print("DSRL QuickBooks Posting Package V10")
    print("=" * 48)

    summary_path = (
        PROCESSED
        / "posting_package_summary_v10.csv"
    )
    lines_path = (
        PROCESSED
        / "posting_package_v10.csv"
    )

    try:
        if not summary_path.exists():
            raise FileNotFoundError(
                "Run build_posting_package_v10.py first."
            )
        if not lines_path.exists():
            raise FileNotFoundError(
                "Run build_posting_package_v10.py first."
            )

        summaries = load_summary(summary_path)
        output_path = (
            OUTPUT / output_filename(summaries)
        )

        export_posting_package(
            summary_path=summary_path,
            lines_path=lines_path,
            output_path=output_path,
        )

    except ModuleNotFoundError as exc:
        if exc.name == "openpyxl":
            print(
                "ERROR: openpyxl is not installed. Run:"
            )
            print(
                "python -m pip install openpyxl"
            )
            return 1
        raise
    except Exception as exc:
        print(
            f"ERROR: Posting Package workbook failed: "
            f"{exc}"
        )
        return 1

    ready = sum(
        1
        for row in summaries
        if row.confidence == "Ready"
    )
    needs_review = len(summaries) - ready

    print(
        f"Payout worksheets:      "
        f"{len(summaries):>6}"
    )
    print(f"Ready:                  {ready:>6}")
    print(
        f"Needs Review:           "
        f"{needs_review:>6}"
    )
    print()
    print(f"Workbook: {output_path}")
    print()
    print(
        "No QuickBooks transactions were created."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
