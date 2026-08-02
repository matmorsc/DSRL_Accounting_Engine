# Phase 11G — Composite Charge Allocation

## Purpose

Handle one Stripe charge that pays for multiple lodging units.

## Current wedding-party allocation

- Room 5: 450.00
- Room 7: 360.00
- A-Frame Cabin: 675.00
- State tax: 37.13
- Fremont County tax: 43.07
- Stripe fee: -45.69
- Net posting effect: 1519.50

Stripe evidence:

- Gross: 1565.19
- Fee: 45.69
- Net: 1519.50

## Files

- `config/composite_charge_allocations_v11.csv`
- `config/composite_charge_approvals_v11.csv`

## Workflow

Run:

```powershell
python -m pytest
python promote_composite_charge_allocation_v11.py
```

Open:

`config/composite_charge_approvals_v11.csv`

Change the wedding-party row:

`Pending` → `Approved`

Preview:

```powershell
python promote_composite_charge_allocation_v11.py
```

Expected:

- allocation total: 1519.50
- net amount: 1519.50
- lines to promote: 6
- validation: Ready to Promote

Apply:

```powershell
python promote_composite_charge_allocation_v11.py --apply
```

Then rebuild downstream posting outputs.
