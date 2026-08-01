# V6 dtype and V5 test-fixture fix

This patch makes no accounting-rule changes.

It fixes:

1. V6 attempted to place a pandas Timestamp into a CSV-loaded string
   `payout_date` column. Exact payout dates are now written as normalized text.
2. The V5 synthetic test fixture defined the source payout as already balanced,
   making the expected residual-based move impossible. The fixture now models
   an actual misplaced -54.32 bundle.

Extract into the project and replace the two files.

Run:

```powershell
python -m pytest
python build_stripe_payout_reconciliation_v6.py
```
