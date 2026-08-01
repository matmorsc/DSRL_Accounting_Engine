# V9 Eligibility and Test Fix

This patch makes two corrections:

1. Ledger-backed deposit drafts are now limited to payouts where the current
   posting-status file has `generate_entry = Yes`. This aligns V9 with the 63
   unposted/eligible legacy drafts and excludes already-posted payouts.
2. The V9 grouping test now expects three grouped lines, because two identical
   Revenue lines correctly collapse into one deposit line.

The runner also prints any payout where V9 performs worse than the legacy draft.

Run:

```powershell
python -m pytest
python build_ledger_deposit_drafts_v9.py
```
