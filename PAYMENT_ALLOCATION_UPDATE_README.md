# DSRL Payment Allocation and Deposit Draft V2

This update adds a payment-event allocation layer and leaves the existing
Deposit Draft Generator untouched.

## Extract

Extract directly into the existing project.

## Added

- `build_deposit_drafts_v2.py`
- `src/posting/payment_allocations.py`
- `src/posting/deposit_drafts_v2.py`
- `tests/test_payment_allocations.py`
- `docs/PAYMENT_ALLOCATIONS.md`

## Run

```powershell
python -m pytest
python run.py
python build_deposit_drafts_v2.py
```

## New outputs

- `data\processed\payment_allocations.csv`
- `data\processed\payment_allocation_diagnostics.csv`
- `data\processed\deposit_drafts_v2.csv`
- `data\processed\deposit_draft_lines_v2.csv`

The old `deposit_drafts.csv` and `deposit_draft_lines.csv` are not replaced.

## What to compare

Compare V1 and V2 counts for:

- Ready for Review
- Review Required
- Balanced Yes
- Balanced No

Then inspect the largest V2 differences and the allocation diagnostics.

## Commit after successful validation

```powershell
git add .
git commit -m "Add payment-event allocation and deposit draft V2"
git push
```
