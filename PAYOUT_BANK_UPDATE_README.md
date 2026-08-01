# Payout and Bank Reconciliation Update

Extract directly into the existing project and replace `run.py`.

Run:

```powershell
python -m pytest
python run.py
```

Expected test count: 12 passed.

New outputs:

- `data\processed\payment_ledger.csv`
- `data\processed\payout_ledger.csv`

The engine now separates payment/refund events from payouts, assigns payment
events to the first payout on or after the available date, summarizes payout
allocation, and matches payouts to bank deposits by processor, amount, and date.

After success:

```powershell
git add .
git commit -m "Add payout allocation and bank reconciliation"
git push
```

Stripe allocation should be strong. Airbnb allocation may still need refinement
for grouped payouts.
