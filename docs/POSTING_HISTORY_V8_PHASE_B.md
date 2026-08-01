# V8 Phase B — Review and Promotion

## Review

Run:

```powershell
python build_posting_history_review.py
```

Output:

`data/processed/posting_history_review.csv`

The review file contains one row per payment event.

Only events with `review_status = Ready for Promotion` may be approved.

Source Event rows are explicitly excluded until Phase C.

To approve an event, change:

`approved_for_promotion`

from:

`Pending`

to:

`Yes`

Do not alter rows marked Review Required or Excluded - Source Event.

## Promotion

Run:

```powershell
python promote_posting_history_v8.py
```

The script first writes:

`data/processed/posting_history_promotion_preview.csv`

It updates the persistent history only after the operator types:

`PROMOTE`

The write is atomic and does not duplicate existing posting-line IDs.

## Idempotence check

After promotion:

```powershell
python build_posting_history_v8.py
```

Approved original lines should no longer be proposed.

Source Event rows will remain proposed until Phase C.
