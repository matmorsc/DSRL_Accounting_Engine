# DSRL Phase 10A — Posting Package Data Model

## Added

- `build_posting_package_v10.py`
- `src/presentation/posting_package.py`
- `tests/test_posting_package_v10.py`
- `docs/POSTING_PACKAGE_V10_PHASE_10A.md`

## Run

```powershell
python -m pytest
python build_posting_package_v10.py
```

The test count should increase by three.

## Outputs

- `data\processed\posting_package_summary_v10.csv`
- `data\processed\posting_package_v10.csv`

## Acceptance test

The Dan Calabro payout should show:

- payout amount: 134.32
- posting total: 134.32
- difference: 0.00
- balanced: Yes
- confidence: Ready

## Safety

No workbook is created yet.
No posting history is modified.
No QuickBooks transactions are created.
