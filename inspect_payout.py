from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.review.payout_inspector import (
    inspect_payout,
    render_inspection,
)


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
CONFIG = ROOT / "config"
OUTPUT = ROOT / "output"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect all available accounting evidence "
            "for a single payout ID."
        )
    )
    parser.add_argument(
        "payout_id",
        help="Processor payout identifier.",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help=(
            "Save the report to output/"
            "payout_inspection_<payout_id>.txt"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        inspection = inspect_payout(
            payout_id=args.payout_id,
            processed_dir=PROCESSED,
            config_dir=CONFIG,
        )
        report = render_inspection(
            inspection
        )
    except Exception as exc:
        print(
            f"ERROR: Payout inspection failed: {exc}"
        )
        return 1

    print(report)

    if args.save:
        OUTPUT.mkdir(
            parents=True,
            exist_ok=True,
        )
        safe_id = "".join(
            character
            if character.isalnum()
            or character in {"-", "_"}
            else "_"
            for character in args.payout_id
        )
        path = (
            OUTPUT
            / f"payout_inspection_{safe_id}.txt"
        )
        path.write_text(
            report,
            encoding="utf-8",
        )
        print()
        print(f"Saved: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
