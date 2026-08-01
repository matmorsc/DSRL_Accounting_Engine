# DSRL V8 Phase B — Review and Promotion

## Added

- `build_posting_history_review.py`
- `promote_posting_history_v8.py`
- `src/posting/history_review.py`
- `src/posting/history_promotion.py`
- `tests/test_posting_history_phase_b.py`
- `docs/POSTING_HISTORY_V8_PHASE_B.md`

## Run

```powershell
python -m pytest
python build_posting_history_review.py
```

The test count should increase by four.

Open:

`data\processed\posting_history_review.csv`

Approve only rows with:

`review_status = Ready for Promotion`

by changing:

`approved_for_promotion = Pending`

to:

`approved_for_promotion = Yes`

Then run:

```powershell
python promote_posting_history_v8.py
```

Review the printed counts and preview. Type `PROMOTE` only when they are correct.

After promotion:

```powershell
python build_posting_history_v8.py
```

Approved originals should disappear from the proposal output.
Source Events remain for Phase C.

No QuickBooks transactions are created.
