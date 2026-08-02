# Phase 11B.1 — Rejected Candidate Diagnostics

## Purpose

Phase 11B.1 explains why a Stripe historical-seed candidate was rejected.

The evidence gate remains unchanged.

## New output

`data/processed/stripe_seed_candidate_diagnostics_v11.csv`

One row per candidate source family, including:

- Stripe gross charge,
- Stripe fee,
- Stripe net charge,
- reservation revenue,
- state tax,
- county tax,
- local tax,
- reservation component total,
- difference between reservation components and Stripe gross,
- diagnostic type,
- detailed explanation,
- possible cause.

## Diagnostic types

- Candidate Ready
- Missing Reservation
- Reservation Gross Mismatch

## Run

```powershell
python -m pytest
python build_stripe_seed_candidates_v11.py
```

No candidates are promoted.
