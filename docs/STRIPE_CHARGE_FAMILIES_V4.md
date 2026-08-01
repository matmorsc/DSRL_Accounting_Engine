# Stripe Charge-Family Pipeline V4

## Why V4 exists

Stripe balance-history exports represent one commercial payment lifecycle with
multiple balance transactions sharing the same `Source` charge ID.

Example:

- charge: +97.08
- refund: -54.54
- adjustment / fee refund: +0.22

The refund and adjustment rows may contain no reservation metadata, but their
shared source identifies the original charge.

## V4 model

V4 groups Stripe rows by:

`processor_account + source_id`

Every component remains a separate event.

The family supplies inherited metadata:

- reservation ID,
- channel reservation ID,
- guest,
- listing.

The family is then assigned to one payout as a unit.

## Safety

V4 is parallel and read-only.

It does not replace the primary pipeline or V1-V3 outputs.

## Run

```powershell
python -m pytest
python build_stripe_charge_families_v4.py
```

## Outputs

- `processor_transactions_v4.csv`
- `stripe_charge_families.csv`
- `stripe_charge_family_diagnostics.csv`
- `payment_ledger_v4.csv`
- `payout_ledger_v4.csv`
- `posting_status_v4.csv`
- `payment_allocations_v4.csv`
- `payment_allocation_diagnostics_v4.csv`
- `deposit_drafts_v4.csv`
- `deposit_draft_lines_v4.csv`

## Known test payout

The runner prints the V4 result for:

`po_1TqjcpJtejknM735RBYtfOau`

Expected bank amount:

`134.32`

The draft should include:

- two positive charge components,
- one negative refund component,
- one positive adjustment component.

No manual payout override should be required.
