# V8 Phase A — Posting History Foundation

Phase A creates a durable posting-history schema and a parallel proposed-history generator.

It does not modify the primary pipeline, overwrite persistent posting history,
generate reversals, create QuickBooks transactions, or resolve remaining exceptions.

Run:

```powershell
python -m pytest
python build_posting_history_v8.py
```

Outputs:

- `data/processed/posting_history_proposed.csv`
- `data/processed/posting_history_diagnostics.csv`

Deterministic IDs ensure repeated runs produce the same posting identities.
Existing posting IDs are not proposed again.
