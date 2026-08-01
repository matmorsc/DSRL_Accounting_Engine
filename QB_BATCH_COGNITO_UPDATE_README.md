# QuickBooks Batch + Cognito Renewal Update

## Before running

Create or use this folder:

`data\raw\cognito\monthly_renewals`

Copy the uploaded Cognito MonthlyRenewal workbook into that folder. Keep its
original contents unchanged; a dated filename is recommended.

Extract this update directly into the project folder and replace `run.py` and
`src\posting\engine.py`.

## Run

```powershell
python -m pytest
python run.py
```

Expected test count: 24 passed.

## New outputs

- `data\processed\quickbooks_posting_batches.csv`
- `data\processed\cognito_renewals.csv`
- `data\processed\legacy_payment_matches.csv`
- Revised `data\processed\posting_status.csv`

## What changed

The QuickBooks posting matcher now recognizes historical Stripe postings that
were entered as:

- One or more A/R payments, deposits, or sales receipts
- Less separate Stripe processing-fee expenses
- Sometimes covering multiple payouts on the same date

It also uses Cognito MonthlyRenewal submissions to identify legacy Stripe
payment events by exact payment amount and submission date.

## Commit after success

```powershell
git add .
git commit -m "Add QuickBooks posting batches and Cognito renewal matching"
git push
```
