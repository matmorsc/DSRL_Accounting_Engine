# Airbnb Payout Assignment and Unlinked Stripe Review

Extract directly into the existing project.

## Replaced

- `src/reconciliation/payouts.py`

## Added

- `src/matching/unlinked_review.py`
- `build_unlinked_stripe_review.py`
- `tests/test_airbnb_unlinked.py`
- `docs/AIRBNB_AND_UNLINKED_REVIEW.md`

## Run

```powershell
python -m pytest
python run.py
python build_deposit_drafts_v2.py
python build_unlinked_stripe_review.py
```

## Expected effect

Airbnb events carrying a payout reference should be assigned to that exact
payout rather than the first same-day payout.

New output:

- `data\processed\unlinked_stripe_review.csv`

The report is advisory only. It does not modify matches or overrides.

## Compare

Compare the new V2 results against the prior counts:

- Ready for Review: 26
- Review Required: 37
- Balanced Yes: 38
- Balanced No: 25

## Commit after validation

```powershell
git add .
git commit -m "Fix Airbnb payout references and add unlinked Stripe review"
git push
```
