# Phase 10A.1 Payout-Ledger Bank Fix

The bank identity now comes from `payout_ledger_v6.csv`, which already contains:

- bank transaction ID,
- bank transaction date,
- bank amount.

`bank_transactions.csv` is used only to enrich the description.

This also updates the stale Phase 10A tests to the new function signature.

Run:

```powershell
python -m pytest
python build_posting_package_v10.py
```
