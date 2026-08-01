# DSRL Stripe Charge-Family V4

This is a parallel validation update. It does not replace the working primary
pipeline.

## Extract

Extract directly into the project folder.

## Added

- `build_stripe_charge_families_v4.py`
- `src/reconciliation/stripe_charge_families.py`
- `src/reconciliation/stripe_family_assignment.py`
- `tests/test_stripe_charge_families.py`
- `docs/STRIPE_CHARGE_FAMILIES_V4.md`

## Run

```powershell
python -m pytest
python build_stripe_charge_families_v4.py
```

The test count should increase by four.

## Review

The runner prints the result for the known Stripe payout:

`po_1TqjcpJtejknM735RBYtfOau`

Upload:

- `data\processed\deposit_drafts_v4.csv`
- `data\processed\stripe_charge_families.csv`
- `data\processed\stripe_charge_family_diagnostics.csv`

Do not promote V4 until the known payout balances and the overall exception
count improves.

## Commit only after validation

```powershell
git add .
git commit -m "Add parallel Stripe charge-family pipeline V4"
git push
```
