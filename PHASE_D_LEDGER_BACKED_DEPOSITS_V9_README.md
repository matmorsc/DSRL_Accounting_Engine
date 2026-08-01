# DSRL Phase D — Ledger-Backed Deposits V9

## Added

- `build_ledger_deposit_drafts_v9.py`
- `src/posting/ledger_deposit_drafts.py`
- `tests/test_ledger_deposit_drafts_v9.py`
- `docs/LEDGER_BACKED_DEPOSITS_V9.md`

## Run

```powershell
python -m pytest
python build_ledger_deposit_drafts_v9.py
```

The test count should increase by three.

## Expected Dan Calabro result

- Payout amount: 134.32
- Legacy draft total: 188.64
- Ledger draft total: 134.32
- Ledger difference: 0.00
- Ledger balanced: Yes
- Comparison status: Improved

## Safety

This is parallel validation only.
No persistent ledger or QuickBooks data is modified.
