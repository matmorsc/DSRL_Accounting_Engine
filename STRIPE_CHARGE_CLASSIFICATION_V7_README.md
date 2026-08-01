# DSRL Stripe Charge Classification V7

This is a parallel validation update.

## Added

- `build_stripe_charge_classification_v7.py`
- `src/reconciliation/stripe_charge_classification.py`
- `src/posting/stripe_historical_allocations.py`
- `config/stripe_charge_classification_ledger.csv`
- `tests/test_stripe_charge_classification.py`
- `docs/STRIPE_CHARGE_CLASSIFICATION_V7.md`

## Run

```powershell
python -m pytest
python build_stripe_charge_classification_v7.py
```

The test count should increase by two.

## Expected known payout

`po_1TqjcpJtejknM735RBYtfOau`

Expected:

- Bank amount: 134.32
- Draft total: 134.32
- Difference: 0.00
- Balanced: Yes

## Important

The proposed classification ledger is written to:

`data\processed\stripe_charge_classification_ledger_v7.csv`

The persistent config ledger is not overwritten during validation.
