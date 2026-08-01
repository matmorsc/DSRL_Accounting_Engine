# DSRL Phase 10B — Posting Package Workbook

## Added

- `build_quickbooks_posting_package_v10.py`
- `src/presentation/posting_workbook.py`
- `tests/test_posting_workbook_v10.py`
- `docs/POSTING_PACKAGE_V10_PHASE_10B.md`

## Required dependency

The workbook generator uses `artifact_tool`.

## Run

```powershell
python -m pytest
python build_quickbooks_posting_package_v10.py
```

The test count should increase by three.

## Output

The workbook is written to:

`output\QuickBooks_Posting_Package_YYYY-MM.xlsx`

It contains:

- one Dashboard worksheet,
- one worksheet per payout,
- clickable navigation,
- exact QuickBooks split instructions,
- bank-feed identity,
- balance formulas,
- review notes.

No QuickBooks transactions are created.
