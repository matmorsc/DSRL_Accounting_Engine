# Airbnb Payout References and Unlinked Stripe Review

## Airbnb assignment change

Payment events now try the strongest available assignment first:

1. Exact processor payout reference (`source_id` equals `payout_id`)
2. First payout on or after the available date

This should prevent multiple same-day Airbnb payouts from swallowing one
another's reservation events.

## Unlinked Stripe review

Run:

```powershell
python build_unlinked_stripe_review.py
```

Output:

- `data/processed/unlinked_stripe_review.csv`

The report lists unresolved Stripe payment events and up to five candidate
Guesty reservations.

Candidate scores use:

- payment amount,
- transaction date versus confirmation/check-in,
- guest-name similarity,
- and listing similarity.

Candidate matches are suggestions only. They do not alter source data or create
overrides.
