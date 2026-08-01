# Posting Date Fix

Extract directly into the existing project and replace:

- `src\posting\engine.py`

New test:

- `tests\test_posting_dates.py`

Then run:

```powershell
python -m pytest
python run.py
```

Expected test count: 21 passed.

This fix safely classifies payouts with missing dates as `Needs Review`
instead of crashing while calling `.normalize()` on `NaT`.

After success:

```powershell
git add .
git commit -m "Handle missing payout dates in posting controls"
git push
```
