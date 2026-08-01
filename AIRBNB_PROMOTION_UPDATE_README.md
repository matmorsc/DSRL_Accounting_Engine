# Airbnb Sequence Promotion Update

This update promotes the validated Airbnb sequence logic into the primary
pipeline and adds a focused deposit-exception review.

## Replaced

- `run.py`

## Added

- `src/reports/deposit_exceptions.py`
- `build_deposit_exception_review.py`
- `tests/test_deposit_exceptions.py`
- `docs/AIRBNB_PROMOTION.md`

## Run

```powershell
python -m pytest
python run.py
python build_deposit_drafts_v2.py
python build_deposit_exception_review.py
```

## Primary outputs added to `run.py`

- `airbnb_sequence_diagnostics.csv`
- `airbnb_sequence_summary.csv`

## New review output

- `deposit_exception_review.csv`

No QuickBooks transactions are created.

## Commit after validation

```powershell
git add .
git commit -m "Promote Airbnb sequence grouping and add deposit exception review"
git push
```
