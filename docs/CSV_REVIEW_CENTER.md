# CSV Review Center

The Review Center resolves historical exceptions without a database.

## Decision files

### Manual payment matches

`config/manual_payment_matches.csv`

One accepted row permanently links a processor payment event to a Guesty or
channel reservation.

### Payout adjustments

`config/payout_adjustments.csv`

One active row adds a documented accounting line to a specific payout draft.

## Run the Review Center

First refresh the review reports:

```powershell
python build_unlinked_stripe_review.py
python build_deposit_exception_review.py
```

Then run:

```powershell
python review_center.py
```

The tool walks through:

1. Unlinked Stripe payment events and suggested reservation candidates.
2. Unexplained payout differences.

Accepted decisions are written immediately to the config CSVs.

## Apply decisions

```powershell
python build_deposit_drafts_v2.py
python build_deposit_exception_review.py
```

The deposit-draft runner now:

- applies accepted manual payment matches before allocation,
- includes active payout adjustments as separate draft lines,
- preserves an override audit column,
- and still refuses to mark an unbalanced draft ready.

## Important control

Do not record a payout adjustment merely because it balances the deposit.

Confirm the cause in Stripe or Airbnb payout detail first, then record the
account, class, description, and evidence in the adjustment CSV.
