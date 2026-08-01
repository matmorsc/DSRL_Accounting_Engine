# Airbnb Sequence Promotion

Airbnb sequence grouping is now part of the primary pipeline.

`python run.py`:

1. Normalizes Airbnb transaction history.
2. Assigns each detail row to the preceding payout row.
3. Generates deterministic IDs for blank historical payout rows.
4. Runs the normal payment, payout, bank, reconciliation, and posting stages.
5. Saves Airbnb sequence diagnostics and summary outputs.

The former V3 command remains available for historical comparison but is no
longer required for routine processing.

## Deposit exception review

After refreshing the pipeline and V2 deposit drafts:

```powershell
python run.py
python build_deposit_drafts_v2.py
python build_deposit_exception_review.py
```

The exception report is:

`data/processed/deposit_exception_review.csv`

It classifies the remaining unresolved payouts by primary cause and recommends
the next review action. It is read-only and does not create QuickBooks entries.
