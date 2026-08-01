# DSRL Airbnb Adjustment Promotion

## Added

- `build_airbnb_adjustment_review.py`
- `promote_airbnb_adjustments.py`
- `src/posting/airbnb_adjustments.py`
- `tests/test_airbnb_adjustment_promotion.py`
- `docs/AIRBNB_ADJUSTMENT_PROMOTION.md`

## Run

```powershell
python -m pytest
python build_airbnb_adjustment_review.py
```

Open:

`data\processed\airbnb_adjustment_review.csv`

Approve the `-12.03` Airbnb fee adjustment by setting:

`approved_for_promotion = Yes`

Then:

```powershell
python promote_airbnb_adjustments.py
```

Type `PROMOTE` after reviewing the preview.

Finally:

```powershell
python build_posting_history_v8.py
python build_ledger_deposit_drafts_v9.py
```

Expected V9 comparison:

- Improved: 1
- Same: 62
- Worse: 0
