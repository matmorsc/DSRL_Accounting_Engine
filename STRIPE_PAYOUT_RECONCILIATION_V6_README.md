# DSRL Stripe Payout Reconciliation V6

This is a parallel validation update. It does not replace the primary pipeline.

## Extract

Extract directly into the project folder.

## Added

- `build_stripe_payout_reconciliation_v6.py`
- `src/importers/stripe_payout_reconciliation.py`
- `src/reconciliation/stripe_payout_membership.py`
- `config/stripe_payout_account_mapping.yaml`
- `tests/test_stripe_payout_reconciliation.py`
- `docs/STRIPE_PAYOUT_RECONCILIATION_V6.md`

## Required raw-data location

The bulk Stripe report must be in:

`data\raw\stripe\payout_reconciliation\`

## Run

```powershell
python -m pytest
python build_stripe_payout_reconciliation_v6.py
```

The test count should increase by three.

## Expected known-payout result

`po_1TqjcpJtejknM735RBYtfOau` should balance at 134.32.

The earlier payout receiving the refund incorrectly should also improve.

## Do not promote yet

Paste the V6 terminal output before committing this as primary logic.
