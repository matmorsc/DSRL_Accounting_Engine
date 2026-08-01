# Phase 10A.1 — Bank-Feed Enrichment

The Posting Package now uses the matched bank transaction as its primary
operational identity.

## Added fields

- processor payout date,
- bank transaction ID,
- bank transaction date,
- bank description,
- bank amount,
- bank difference,
- bank balance status.

## Primary display behavior

Worksheet names and bank-feed labels use the bank transaction date when
available.

Example:

`Stripe - 2026-07-10`

instead of the processor payout date:

`Stripe - 2026-07-08`

## Confidence

A package is Ready only when:

- the ledger-backed draft is Ready for Review,
- the posting total matches the bank transaction amount,
- and the result is Same or Improved versus legacy.

## Run

```powershell
python -m pytest
python build_posting_package_v10.py
```

No workbook is created yet.
No posting history or QuickBooks data is modified.
