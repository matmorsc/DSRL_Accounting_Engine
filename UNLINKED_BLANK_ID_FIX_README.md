# Unlinked Stripe Blank-ID Fix

The review engine incorrectly treated blank reservation IDs as valid links when
the Guesty dataset also contained blank channel IDs.

This update:

- excludes blank IDs from lookup sets,
- requires a nonblank ID before considering an event linked,
- and preserves the full output schema even when the review is empty.

Extract into the existing project and replace:

- `src\matching\unlinked_review.py`

Added:

- `tests\test_unlinked_blank_ids.py`

Run:

```powershell
python -m pytest
python build_unlinked_stripe_review.py
```

The unlinked Stripe count should increase materially from the incorrect count of
6.

Then upload:

- `data\processed\unlinked_stripe_review.csv`
- `data\processed\processor_transactions.csv`

The processor transactions file is needed to inspect which Airbnb source column
actually contains the payout grouping information.
