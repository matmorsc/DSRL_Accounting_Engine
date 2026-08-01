# DSRL V8 Phase C — Reversal Preview

## Added

- `build_posting_history_reversals_v8.py`
- `src/posting/history_reversals.py`
- `tests/test_posting_history_reversals.py`
- `config/posting_history_manual_seeds.csv`
- `docs/POSTING_HISTORY_V8_PHASE_C.md`

## Run

```powershell
python -m pytest
python build_posting_history_reversals_v8.py
```

The test count should increase by four.

## Outputs

- `data\processed\posting_history_reversal_preview.csv`
- `data\processed\posting_history_reversal_review.csv`

The known Dan Calabro source is expected to appear in the review queue if its
original charge is absent from persistent posting history. That is a correct
control result, not a failure.

No persistent posting history is modified.
No QuickBooks transactions are created.
