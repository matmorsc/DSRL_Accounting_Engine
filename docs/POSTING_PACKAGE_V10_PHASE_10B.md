# Phase 10B — QuickBooks Posting Package Workbook

## Purpose

Phase 10B converts the canonical V10 Posting Package datasets into the workbook
used beside QuickBooks Bank Transactions.

## Inputs

- `data/processed/posting_package_summary_v10.csv`
- `data/processed/posting_package_v10.csv`

## Output

`output/QuickBooks_Posting_Package_YYYY-MM.xlsx`

## Dashboard

The Dashboard includes:

- payout counts,
- Ready and Needs Review counts,
- total bank amount,
- total posting amount,
- one row per payout,
- confidence status,
- bank-feed identity,
- differences,
- review notes,
- clickable links to payout worksheets.

## Payout worksheets

Each payout worksheet includes:

- bank-feed date and description,
- bank amount,
- posting total,
- difference,
- confidence,
- processor payout date,
- payout and bank identifiers,
- exact QuickBooks category/class/description/amount split lines,
- formula-driven split total,
- formula-driven difference to bank,
- explanatory notes,
- link back to the Dashboard.

## Run

```powershell
python -m pytest
python build_quickbooks_posting_package_v10.py
```

No QuickBooks transactions are created.
