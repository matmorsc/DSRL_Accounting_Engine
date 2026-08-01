# QuickBooks Batch Test Fix

Extract directly into the existing project and replace:

- `tests\test_posting.py`
- `tests\test_posting_dates.py`

Then run:

```powershell
python -m pytest
python run.py
```

Expected result:

- 24 passed
- The same posting summary as before

After success:

```powershell
git add .
git commit -m "Update posting tests for QuickBooks batches"
git push
```
