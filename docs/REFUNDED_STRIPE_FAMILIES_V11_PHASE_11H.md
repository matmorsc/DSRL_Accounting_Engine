# Phase 11H — Fully Refunded Stripe Families

## Purpose

Resolve Stripe charge families where:

- the original charge exists;
- the reservation was fully refunded;
- no revenue or customer payment remains;
- Stripe retained the processing fee;
- Stripe may have issued a fee adjustment.

No replacement revenue posting is created.

## Ryan Staab

Stripe family:

- charge net: 279.99
- refund: -289.86
- adjustment: 1.16
- family net: -8.71

Posting history:

- retained Stripe processing fee: -9.87
- Stripe fee adjustment credit: 1.16
- net source-event effect: -8.71

## Workflow

Run:

```powershell
python -m pytest tests\test_refunded_stripe_families_v11.py -q
python promote_refunded_stripe_families_v11.py
```

Open:

`config/refunded_stripe_family_approvals_v11.csv`

Approve only Ryan Staab's eligible family.

Preview:

```powershell
python promote_refunded_stripe_families_v11.py
```

Apply:

```powershell
python promote_refunded_stripe_families_v11.py --apply
```

Then rebuild the downstream posting package.
