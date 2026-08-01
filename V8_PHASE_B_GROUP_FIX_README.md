# V8 Phase B Posting-Group Fix

Extract into the project and replace:

- `src/posting/history_review.py`
- `src/posting/history_promotion.py`

Added:

- `tests/test_posting_history_group_review.py`
- `docs/POSTING_HISTORY_V8_PHASE_B_GROUP_FIX.md`

Run:

```powershell
python -m pytest
python build_posting_history_review.py
```

Expected review:

- the Airbnb reservation group is `Ready for Promotion`,
- the Airbnb adjustment group remains `Excluded - Source Event`.

Approve only the reservation group's `posting_group_id`, then run:

```powershell
python promote_posting_history_v8.py
python build_posting_history_v8.py
```

After promotion, only the 13 Source Event lines should remain proposed.
