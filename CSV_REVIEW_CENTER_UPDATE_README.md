# DSRL CSV Review Center Update

This update adds a local, CSV-backed operator interface. No SQL or database is
introduced.

## Added

- `review_center.py`
- `src/review/overrides.py`
- `src/review/__init__.py`
- `config/manual_payment_matches.csv`
- `config/payout_adjustments.csv`
- `tests/test_csv_review_center.py`
- `docs/CSV_REVIEW_CENTER.md`

## Replaced

- `build_deposit_drafts_v2.py`
- `src/posting/deposit_drafts_v2.py`

## Install and test

Extract into the project folder, then run:

```powershell
python -m pytest
```

The test count should increase by three.

## Review workflow

```powershell
python build_unlinked_stripe_review.py
python build_deposit_exception_review.py
python review_center.py
```

After saving decisions:

```powershell
python build_deposit_drafts_v2.py
python build_deposit_exception_review.py
```

## Safety

- No QuickBooks transactions are created.
- Decisions are stored in Git-trackable CSV files.
- Manual matches can be deactivated by changing `status`.
- Payout adjustments require an exact account and class.
- The review tool does not invent an adjustment cause.

## Commit

```powershell
git add .
git commit -m "Add CSV review center for payment matches and payout adjustments"
git push
```
