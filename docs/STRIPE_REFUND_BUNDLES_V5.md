# Stripe Refund-Bundle Pipeline V5

## Correction to V4

A Stripe Source identifies the underlying charge family, but a charge family can
span multiple payouts.

V5 therefore uses Source for metadata inheritance only.

It does not force the original charge, refund, and adjustment into one payout.

## Refund bundles

V5 groups refund-related Stripe balance rows when they share:

- processor account,
- Source charge ID,
- and exact transaction timestamp.

Example:

- refund: -54.54
- adjustment / fee refund: +0.22
- bundle net: -54.32

## Residual assignment

A bundle moves only when:

1. Removing it balances its current payout within tolerance.
2. Adding it balances exactly one destination payout within tolerance.
3. The combined absolute residual improves.
4. The candidate payout is within 30 days.

If zero or multiple exact destinations exist, no move occurs and the bundle is
flagged for review.

## Safety

V5 is parallel. It does not replace V1-V4 or create QuickBooks transactions.

## Run

```powershell
python -m pytest
python build_stripe_refund_bundles_v5.py
```

The runner reports both known payouts affected by the -54.32 bundle.
