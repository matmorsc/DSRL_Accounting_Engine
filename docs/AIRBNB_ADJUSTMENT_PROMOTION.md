# Standalone Airbnb Adjustment Promotion

Valid standalone Airbnb adjustment lines can be promoted into persistent posting
history without using reversal logic.

Eligibility:

- processor is Airbnb,
- transaction type is adjustment,
- posting type is Source Event,
- payout ID is present,
- account and class are present,
- total is nonzero.

Stripe refunds and other source-event types are excluded.

Run:

```powershell
python build_airbnb_adjustment_review.py
```

Approve only rows marked `Ready for Promotion` by changing:

`approved_for_promotion = Pending`

to:

`approved_for_promotion = Yes`

Then run:

```powershell
python promote_airbnb_adjustments.py
```

After promotion:

```powershell
python build_posting_history_v8.py
python build_ledger_deposit_drafts_v9.py
```
