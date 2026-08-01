# DSRL V8 Phase A — Posting History

Added:

- `build_posting_history_v8.py`
- `src/posting/history.py`
- `config/posting_history.csv`
- `tests/test_posting_history_v8.py`
- `docs/POSTING_HISTORY_V8_PHASE_A.md`

Run:

```powershell
python -m pytest
python build_posting_history_v8.py
```

The test count should increase by three.

The persistent history file is not modified by the generator.
No QuickBooks transactions are created.
