# DSRL Stripe Refund-Bundle V5

This update corrects the failed V4 approach.

## Added

- `build_stripe_refund_bundles_v5.py`
- `src/reconciliation/stripe_refund_bundles.py`
- `tests/test_stripe_refund_bundles.py`
- `docs/STRIPE_REFUND_BUNDLES_V5.md`

## Run

```powershell
python -m pytest
python build_stripe_refund_bundles_v5.py
```

The test count should increase by four.

## Expected known-payout result

Both should balance:

- `po_1TqjcpJtejknM735RBYtfOau`
- `po_1TqMRVJtejknM735LuF9w3hi`

## Outputs

- `payment_ledger_v5.csv`
- `stripe_refund_bundle_diagnostics.csv`
- `payout_ledger_v5.csv`
- `posting_status_v5.csv`
- `payment_allocations_v5.csv`
- `payment_allocation_diagnostics_v5.csv`
- `deposit_drafts_v5.csv`
- `deposit_draft_lines_v5.csv`

Do not promote V5 until the two known payouts and overall counts improve.
