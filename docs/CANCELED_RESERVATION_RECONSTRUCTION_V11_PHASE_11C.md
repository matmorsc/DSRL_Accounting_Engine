# Phase 11C — Evidence-Based Canceled Reservation Reconstruction

## Purpose

Guesty preserves payment and refund totals for canceled reservations but zeros
out their original accommodation and tax allocation.

Phase 11C introduces two narrowly approved reconstruction paths.

## Approved fallback 1: Booking.com motel

Requirements:

- reservation exists;
- listing is a lodge room;
- source is Booking.com;
- normalized allocation is zero;
- Guesty `total_paid`, `total_refunded`, or `total_payout` confirms the Stripe
  gross exactly.

Allocation:

- full Stripe gross to motel revenue;
- Stripe fee as a negative processing-fee line.

Evidence level: High.

## Approved fallback 2: VRBO/HomeAway motel

Requirements:

- reservation exists;
- listing is a lodge room;
- source is VRBO or homeaway2;
- normalized allocation is zero;
- Guesty payment/refund evidence confirms Stripe gross;
- exactly one penny-level allocation exists using:
  - 2.9% lodging tax;
  - 2.5% lodging tax.

Evidence level: High.

## Explicitly excluded

Website RV cancellations are not automatically reconstructed. Gross payment may
be confirmed, but the allocation is not uniquely supported by the evidence.

Missing reservations remain blocked.

## Audit fields

Candidate lines now preserve:

- allocation method;
- evidence level;
- evidence source;
- evidence reason;
- generator version.

## Run

```powershell
python -m pytest
python build_stripe_seed_candidates_v11.py
```

No candidates are promoted automatically.
