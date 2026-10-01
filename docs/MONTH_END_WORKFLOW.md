# DSRL Month-End Accounting Workflow

This is the operator guide for running the DSRL Accounting Engine from fresh
exports through the QuickBooks posting package.

The engine does not create QuickBooks transactions.

## Workflow Summary

```text
Refresh exports
     ↓
python build_month_end_package.py
     ↓
Promotion gate?
     ↓
Review posting_history_review.csv
     ↓
Approve only Ready for Promotion rows
     ↓
python promote_posting_history_v8.py
     ↓
PROMOTE
     ↓
python build_month_end_package.py
     ↓
Review balanced deposit drafts
     ↓
Review QuickBooks workbook
     ↓
Enter approved entries into QuickBooks
     ↓
Refresh QuickBooks export
```

## Before You Start

Refresh the current source exports under `data/raw/`.

Typical sources:

- Guesty reservations
- Stripe Main
- Stripe Cognito
- Stripe Keycheck
- Airbnb
- Bank
- QuickBooks general ledger
- QuickBooks chart of accounts / inventory
- Cognito monthly renewals, when available

Do not silently substitute old exports for current ones.

## Month-End Orchestrator

Run the complete workflow from the repository root:

```powershell
python build_month_end_package.py
```

The orchestrator runs these stages in order:

1. `run.py`
2. `build_stripe_payout_reconciliation_v6.py`
3. `build_posting_history_v8.py`
4. `build_posting_history_review.py`
5. posting-history promotion gate
6. `build_posting_history_reversals_v8.py`
7. `build_ledger_deposit_drafts_v9.py`
8. `build_posting_package_v10.py`
9. `build_quickbooks_posting_package_v10.py`

Do not use `run.py` alone when the objective is the complete month-end posting
package.

## Why the Promotion Gate Exists

V9 deposit drafts rely on persistent posting history in
`config/posting_history.csv`.

The engine can generate correct original posting lines in
`data/processed/posting_history_proposed.csv`, but those lines are not part of
the V9 ledger until they are explicitly reviewed and promoted.

The promotion gate prevents the workflow from building V9 deposits when
`data/processed/posting_history_review.csv` still contains rows where:

- `review_status = Ready for Promotion`
- `approved_for_promotion != Yes`

`Review Required` rows do not trigger this gate.

`Excluded - Source Event` rows do not trigger this gate.

## What to Do When the Gate Stops the Workflow

1. Open `data/processed/posting_history_review.csv`.
2. Review the rows.
3. Approve only rows where `review_status = Ready for Promotion`.
4. Do not approve `Review Required` rows.
5. Do not approve `Excluded - Source Event` rows.
6. Run:

   ```powershell
   python promote_posting_history_v8.py
   ```

7. At the prompt, type exactly:

   ```text
   PROMOTE
   ```

8. Rerun:

   ```powershell
   python build_month_end_package.py
   ```

The promotion step updates `config/posting_history.csv`. The month-end build
itself does not auto-approve or auto-promote anything.

## Reviewing the Outputs

Important review artifacts:

- `data/processed/posting_history_review.csv`
- `data/processed/deposit_drafts_v9.csv`
- `data/processed/deposit_draft_lines_v9.csv`
- `data/processed/deposit_draft_comparison_v9.csv`
- `data/processed/posting_package_v10.csv`
- `output/QuickBooks_Posting_Package_YYYY-MM.xlsx`

For a V9 payout draft, review at least:

- `payout_amount`
- `ledger_total`
- `difference`
- `balanced`
- `draft_status`

A balanced payout should look like this:

```text
payout_amount = 380.03
ledger_total   = 380.03
difference     = 0.00
balanced       = Yes
```

Generating the workbook does not mean entries have been posted to QuickBooks.

## QuickBooks Posting

The generated workbook is a review package only.

- The engine does not create QuickBooks transactions.
- Generating the workbook does not mark payouts as posted.
- QuickBooks exports should be refreshed after the entries are actually posted.

After entering approved entries into QuickBooks:

1. Refresh/export the QuickBooks general ledger.
2. Place the updated export under `data/raw/quickbooks/`.
3. Use the refreshed export on the next engine run.

If QuickBooks is not refreshed after actual posting, previously posted payouts
can be proposed again.

## September 2026 Example

The promotion gate exists to prevent a repeat of the September 2026 workflow
issue.

Stripe payout `po_1UFO7YJtejknM735epbclImS` had an actual payout of `$380.03`.
The original Paul Wood and Wendy Schott posting lines had been generated
correctly in proposed posting history, but they had not yet been promoted into
`config/posting_history.csv`.

Because V9 reads persistent posting history, the deposit draft could be built
from incomplete persistent history if promotion had not happened yet.

After promotion, the payout reconciled exactly:

```text
payout_amount = 380.03
ledger_total   = 380.03
difference     = 0.00
balanced       = Yes
```

That is the intended workflow:

```text
propose
  ↓
review
  ↓
promote
  ↓
persistent history
  ↓
V9 deposit draft
  ↓
QuickBooks posting package
```