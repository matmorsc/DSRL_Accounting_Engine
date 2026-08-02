# Phase 11F — Evidence-Based Original Charge Reconstruction

## Purpose

Reconstruct original Stripe charge posting history when:

- Stripe proves the charge;
- reservation allocation fields are zero;
- no refund was recorded;
- applicable tax rates are known.

## Tax configuration

`config/tax_rates_v11.csv`

Current values:

- state: 2.5%
- local: 2.9%

## Johnathon Zawadzki

Expected reconstruction:

- RV Rent - Nightly: 109.97
- State lodging tax: 2.75
- Local lodging tax: 3.19
- Stripe processing fee: -4.12
- Net posting effect: 111.79

## Workflow

Run:

```powershell
python -m pytest
python promote_original_charge_reconstruction_v11.py
```

Open:

`config/original_charge_reconstruction_approvals_v11.csv`

Approve only the Johnathon Zawadzki row.

Preview:

```powershell
python promote_original_charge_reconstruction_v11.py
```

Apply:

```powershell
python promote_original_charge_reconstruction_v11.py --apply
```

Then rebuild downstream posting outputs.
