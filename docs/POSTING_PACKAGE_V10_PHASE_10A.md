# Phase 10A — Posting Package Data Model

## Purpose

Phase 10A creates the canonical presentation-layer datasets used by future
Excel, web, PDF, and QuickBooks-import interfaces.

It does not change accounting logic.

## Inputs

- `data/processed/deposit_drafts_v9.csv`
- `data/processed/deposit_draft_lines_v9.csv`
- `data/processed/deposit_draft_comparison_v9.csv`

## Outputs

### Summary

`data/processed/posting_package_summary_v10.csv`

One row per payout, including:

- processor,
- payout date and amount,
- posting total,
- difference,
- balance status,
- review status,
- confidence,
- legacy comparison,
- worksheet name,
- bank-feed label,
- human-readable review notes.

### Lines

`data/processed/posting_package_v10.csv`

One row per QuickBooks split line, including:

- payout metadata,
- account,
- class,
- description,
- amount,
- posting type,
- ledger source,
- line-level notes.

## Confidence

`Ready`

means:

- the payout is balanced,
- the ledger-backed draft is ready for review,
- and the result is Same or Improved versus the legacy draft.

Anything else is:

`Needs Review`

## Run

```powershell
python -m pytest
python build_posting_package_v10.py
```

No workbook is created in Phase 10A.
No posting history or QuickBooks data is modified.
