# DSRL Phase 10A.1 — Bank-Feed Enrichment

## Replaces

- `build_posting_package_v10.py`
- `src/presentation/posting_package.py`

## Adds

- `tests/test_posting_package_bank_feed.py`
- `docs/POSTING_PACKAGE_V10_PHASE_10A1.md`

## Run

```powershell
python -m pytest
python build_posting_package_v10.py
```

The test count should increase by three.

## Acceptance test

For the Dan Calabro payout, the package should print:

- processor payout date,
- bank transaction date,
- bank description,
- bank amount,
- posting total,
- bank difference 0.00,
- bank balanced Yes,
- confidence Ready,
- sheet name based on the bank date.

No workbook or QuickBooks transaction is created.
