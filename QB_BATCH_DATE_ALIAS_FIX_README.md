# QuickBooks Batch Date Alias Fix

The batch engine now accepts either:

- `transaction_date` or `batch_date`
- `batch_id` or `qb_batch_id`
- `processor` or `identified_processor`

It also preserves combined same-day payout matching.

Extract into the existing project and replace:

- `src\posting\engine.py`

New test:

- `tests\test_posting_batch_date_alias.py`

Run:

```powershell
python -m pytest
python run.py
```

Expected result:

- 28 passed
- Real-data run completes

After success:

```powershell
git add .
git commit -m "Support QuickBooks batch date and ID aliases"
git push
```
