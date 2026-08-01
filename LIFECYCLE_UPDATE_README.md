# Lifecycle Reconciliation Update

Extract directly into the existing project and replace:

- `run.py`
- `src\reconciliation\engine.py`

New file:

- `tests\test_lifecycle.py`

Run:

```powershell
python -m pytest
python run.py
```

Expected test count: 16 passed.

`reconciliation.csv` will now include:

- payment_status
- payout_ids
- payout_dates
- payout_status
- bank_transaction_ids
- bank_deposit_dates
- bank_status
- lifecycle_status
- review_required

Final lifecycle statuses include:

- Fully Reconciled
- Payout Pending
- Payout Allocation Review
- Deposit Missing or Review
- Expected Future Airbnb Payment
- Expected Future Manual Payment
- Booking.com Collection Issue
- Payment Amount Mismatch
- Refund Discrepancy
- No Payment Source Found

After successful tests and execution:

```powershell
git add .
git commit -m "Add reservation payout and bank lifecycle statuses"
git push
```
