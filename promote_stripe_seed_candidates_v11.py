from __future__ import annotations

import argparse
import sys
from pathlib import Path
import pandas as pd

from src.review.stripe_seed_promotion import apply_stripe_seed_promotion, preview_stripe_seed_promotion

ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
CONFIG = ROOT / "config"


def read_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def read_optional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    approvals_path = CONFIG / "stripe_seed_approvals_v11.csv"
    candidates_path = PROCESSED / "stripe_seed_candidates_v11.csv"
    history_path = CONFIG / "posting_history_manual_seeds.csv"
    preview_path = PROCESSED / "stripe_seed_promotion_preview_v11.csv"

    print("DSRL Stripe Seed Promotion - Phase 11D")
    print("=" * 58)
    try:
        approvals = read_required(approvals_path)
        candidates = read_required(candidates_path)
        history = read_optional(history_path)
        if args.apply:
            preview, updated_history, updated_approvals = apply_stripe_seed_promotion(
                approvals=approvals, candidates=candidates, existing_history=history
            )
            preview.to_csv(preview_path, index=False)
            updated_history.to_csv(history_path, index=False)
            updated_approvals.to_csv(approvals_path, index=False)
        else:
            preview, _ = preview_stripe_seed_promotion(
                approvals=approvals, candidates=candidates, existing_history=history
            )
            preview.to_csv(preview_path, index=False)
    except Exception as exc:
        print(f"ERROR: Stripe seed promotion failed: {exc}")
        return 1

    print(f"Approved candidate groups:  {(approvals['approval_status'].astype(str).str.strip() == 'Approved').sum():>6}")
    print(f"Preview groups:             {len(preview):>6}")
    if not preview.empty:
        print("\nPromotion controls\n" + "-" * 58)
        print(preview[["payout_id", "guest", "listing", "validation_status", "candidate_total", "expected_effect", "lines_to_promote", "validation_detail"]].to_string(index=False))
    print(f"\nPreview: {preview_path}")
    if args.apply:
        print(f"Promoted posting lines:     {int(pd.to_numeric(preview['lines_to_promote'], errors='coerce').fillna(0).sum()):>6}")
        print(f"History: {history_path}")
        print("Approved candidates were promoted.")
    else:
        print("Preview only. No posting history was modified.")
        print("Run again with --apply after reviewing the preview.")
    print("No QuickBooks transactions were created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
