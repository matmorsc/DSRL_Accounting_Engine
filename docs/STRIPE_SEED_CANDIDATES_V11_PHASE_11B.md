# Phase 11B — Stripe Seed Candidate Generator

## Purpose

Phase 11B creates proposed historical original-charge posting lines only for
Stripe exceptions that are:

- High confidence,
- exact matches,
- sign-safe,
- not blocked,
- explicitly recommended for evidence-backed seed creation.

## Evidence requirements

A candidate group is approval-eligible only when:

1. A matching normalized reservation exists.
2. Reservation revenue and taxes equal the Stripe gross charge.
3. The Stripe processing fee is included as a negative posting line.
4. The total proposed seed effect exactly offsets the payout difference.
5. The proposed effect moves the payout toward balance.

## Outputs

### Proposed posting lines

`data/processed/stripe_seed_candidates_v11.csv`

### Approval controls

`config/stripe_seed_approvals_v11.csv`

All eligible rows begin with:

`approval_status = Pending`

## Run

```powershell
python -m pytest
python build_stripe_seed_candidates_v11.py
```

No candidates are promoted in Phase 11B.
