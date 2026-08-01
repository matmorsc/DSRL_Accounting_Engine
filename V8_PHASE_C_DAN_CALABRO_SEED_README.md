# V8 Phase C — Dan Calabro Seed

Extract into the project folder.

Replaces:

- `config/posting_history_manual_seeds.csv`
- `build_posting_history_reversals_v8.py`

Adds:

- `tests/test_posting_history_manual_seed.py`
- `docs/POSTING_HISTORY_V8_DAN_CALABRO_SEED.md`

Run:

```powershell
python -m pytest
python build_posting_history_reversals_v8.py
```

Expected Dan Calabro acceptance result:

- Reversal lines: 4
- Net reversal: -54.32
- Balanced target: Yes

No persistent posting history is modified.
No QuickBooks transactions are created.
