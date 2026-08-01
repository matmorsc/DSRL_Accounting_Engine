# Stripe Charge Classification Ledger V7

## Purpose

Guesty is an operational system and may stop returning historical reservations.

Stripe retains the relationship between:

- original charge,
- refund,
- adjustment,
- and payout.

V7 classifies each Stripe charge once and stores the accounting classification
by Stripe Source charge ID.

Refund-like events reuse that original classification instead of requiring the
reservation to remain present in the latest Guesty export.

## Persistent file

`config/stripe_charge_classification_ledger.csv`

The V7 validation runner does not overwrite this file. It writes a proposed
ledger to:

`data/processed/stripe_charge_classification_ledger_v7.csv`

Only after validation should the proposed ledger be promoted to config.

## Allocation logic

For an unallocated Stripe refund or adjustment:

1. Find its `processor_account + source_id`.
2. Look up the original charge classification.
3. Apply the refund amount across revenue and tax using the original charge's
   saved component shares.
4. Preserve the original income account and QuickBooks class.
5. Keep the event's actual sign.

## Run

```powershell
python -m pytest
python build_stripe_charge_classification_v7.py
```

No QuickBooks transactions are created.
