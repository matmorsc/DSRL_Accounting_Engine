# V8 Phase C — Reversal Preview

Phase C reads Stripe refund-like events and reverses persistent Original posting
history by `processor_account + source_id`.

## Rules

- Refund, reversal, and dispute events reverse positive Original posting lines.
- Adjustment events reverse negative Original posting lines, such as Stripe
  processing-fee expense.
- Reversal amounts preserve the source event's actual signed amount.
- Reversal lines reference the exact original `posting_line_id`.
- IDs are deterministic.
- Existing Reversal events are not proposed again.

## Missing original history

If no active Original posting lines exist for a Stripe Source, the event is sent
to:

`data/processed/posting_history_reversal_review.csv`

The engine does not invent the original accounting.

A header-only manual seed file is included:

`config/posting_history_manual_seeds.csv`

The next step after the preview is to create and approve evidence-backed
original-history seeds for missing historical charges, then rerun Phase C.

## Run

```powershell
python -m pytest
python build_posting_history_reversals_v8.py
```

No persistent history or QuickBooks data is modified.
