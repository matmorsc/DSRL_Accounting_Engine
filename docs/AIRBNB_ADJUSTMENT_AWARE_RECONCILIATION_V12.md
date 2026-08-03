# Airbnb Adjustment-Aware Reconciliation — V12

## Purpose

Complete the existing Airbnb adjustment workflow so that payout-level events are preserved and can be reviewed, approved, promoted, and included in ledger-backed deposits.

## Corrected behavior

Airbnb exports use different money columns by row type:

- `reservation`: `Gross earnings` and `Amount`
- `payout`: `Paid out`
- `adjustment`, `resolution adjustment`, and `cancellation fee`: `Gross earnings` and `Amount`

The prior importer used `Paid out` for every non-reservation row. Airbnb commonly leaves that field blank or zero on adjustment rows, causing the engine to lose their payout effect.

V12 also treats these transaction types as source events:

- `adjustment`
- `resolution adjustment`
- `cancellation fee`

They flow through the existing review and promotion controls rather than a new subsystem.

## Workflow

After installing the patch, rerun the normal build from raw data so `processor_transactions.csv`, `payment_ledger_v6.csv`, allocations, and proposed posting history are regenerated.

Then:

```powershell
python build_airbnb_adjustment_review.py
```

Review:

```text
data\processed\airbnb_adjustment_review.csv
```

Approve the intended rows by changing `approved_for_promotion` from `Pending` to `Yes`.

Promote:

```powershell
python promote_airbnb_adjustments.py
```

Type `PROMOTE` when prompted, then rebuild the downstream package.
