# Phase D — Ledger-Backed Deposit Drafts V9

## Purpose

V9 builds deposit posting batches from the engine's accounting ledger rather
than reconstructing accounting from reservations and processor events.

## Ledger sources

V9 combines:

- active rows from `config/posting_history.csv`,
- active rows from `config/posting_history_manual_seeds.csv`,
- proposed Reversal rows from
  `data/processed/posting_history_reversal_preview.csv`.

Manual seed rows with blank payout IDs are retained as historical basis but do
not enter current deposit batches. Their generated reversal rows do.

## Outputs

- `data/processed/ledger_lines_v9.csv`
- `data/processed/deposit_drafts_v9.csv`
- `data/processed/deposit_draft_lines_v9.csv`
- `data/processed/deposit_draft_comparison_v9.csv`

## Comparison

Each ledger-backed draft is compared with the legacy V6 draft:

- Improved
- Same
- Worse
- Ledger Only

## Acceptance test

For payout:

`po_1TqjcpJtejknM735RBYtfOau`

Expected:

- payout amount: 134.32
- legacy draft: 188.64
- ledger draft: 134.32
- ledger difference: 0.00
- comparison: Improved

## Safety

The primary deposit builder is not replaced.
Persistent history is not modified.
No QuickBooks transactions are created.
