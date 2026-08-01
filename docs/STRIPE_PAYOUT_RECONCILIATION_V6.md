# Stripe Payout Reconciliation V6

## Purpose

The existing Stripe balance-history export remains the primary transaction and
reservation-metadata source.

The itemized payout reconciliation report supplies the missing authoritative
relationship:

`balance_transaction_id -> automatic_payout_id`

V6 joins that relationship to the existing payment ledger:

`payment_ledger.transaction_id = membership.balance_transaction_id`

## Folder

Place one or more report CSV files in:

`data/raw/stripe/payout_reconciliation/`

The importer reads all CSV files in that folder and subfolders.

## Account mapping

Stripe report account names are mapped to the engine's processor-account names
in:

`config/stripe_payout_account_mapping.yaml`

Current mapping:

`DSRL - Guesty -> Main Guesty`

Additional Stripe accounts can be added later without changing code.

## Precedence

1. Exact payout reconciliation membership
2. Existing fallback payout assignment for uncovered rows

The exact report never changes reservation classification or accounting
allocation. It only corrects payout membership.

## Run

```powershell
python -m pytest
python build_stripe_payout_reconciliation_v6.py
```

## Outputs

- `stripe_payout_membership.csv`
- `stripe_payout_membership_diagnostics.csv`
- `payment_ledger_v6.csv`
- `payout_ledger_v6.csv`
- `posting_status_v6.csv`
- `payment_allocations_v6.csv`
- `payment_allocation_diagnostics_v6.csv`
- `deposit_drafts_v6.csv`
- `deposit_draft_lines_v6.csv`

No QuickBooks transactions are created.
