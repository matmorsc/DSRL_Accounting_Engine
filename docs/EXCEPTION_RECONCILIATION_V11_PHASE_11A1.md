# Phase 11A.1 — Exception Evidence Reconciliation

## Purpose

Phase 11A.1 determines whether each proposed exception resolution is supported
by the transaction math.

It adds a sign-consistency control:

- if posting total is too low, a valid correction must increase it;
- if posting total is too high, a valid correction must reduce it.

This prevents a "missing original charge" classification from automatically
creating a positive seed when the payout already has excess posting.

## Outputs

### Reconciliation summary

`data/processed/exception_reconciliation_summary_v11.csv`

One row per exception with:

- authoritative event total,
- active-history total,
- reversal-preview total,
- unposted-event total,
- reconciled gap,
- exact-match status,
- evidence confidence,
- sign-consistency result,
- resolution-blocked flag,
- recommended resolution.

### Stripe family reconciliation

`data/processed/stripe_family_reconciliation_v11.csv`

One row per Stripe payout/source family with:

- charge, refund, adjustment, and other totals,
- active original and adjustment history,
- reversal preview total,
- family gap,
- issue classification,
- candidate resolution,
- sign-safety control.

### Airbnb component reconciliation

`data/processed/airbnb_component_reconciliation_v11.csv`

One row per Airbnb payment event with:

- event total,
- active-history total,
- component gap,
- component status,
- candidate resolution,
- exact-difference-candidate flag.

## Run

```powershell
python -m pytest
python build_exception_reconciliation_v11.py
```

No resolutions are applied.
