# DSRL Month-End Runbook

## Authoritative procedure

1. Put the current exports in the documented `data/raw` folders. Keep dated
   filenames and do not overwrite earlier exports.
2. Activate the project environment and run the tests:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   python -m pytest
   ```

3. Build the complete posting package:

   ```powershell
   python build_month_end_package.py
   ```

The command stops at the first failed stage. It rebuilds, in order:

1. canonical normalized ledgers and posting status from current raw exports;
2. exact Stripe payout membership, current V6 ledgers, allocations, and legacy
   comparison drafts;
3. proposed posting history for review without changing persistent history;
4. reversal preview from the current payment ledger;
5. ledger-backed V9 deposit drafts;
6. V10 posting-package CSV files; and
7. `output/QuickBooks_Posting_Package_YYYY-MM.xlsx`.

Each downstream command checks that its required derived inputs are at least as
new as their upstream inputs. A stale file causes the build to stop with the
command that must regenerate it.

## Review controls

- Review unresolved and `Needs Review` rows before using the workbook.
- Only payouts with `generate_entry = Yes` enter ledger-backed drafts.
- The workflow reads `config/posting_history.csv` and approved manual seeds; it
  does not modify persistent posting history.
- The workbook is a review package. It does not create QuickBooks transactions.

## After Posting to QuickBooks

> **Generating the workbook does not mark its payouts as posted.** After
> entering entries in QuickBooks, refresh the QuickBooks exports before the
> next month-end run, or record an appropriate `Already Posted` manual
> override. Otherwise, those payouts may be proposed again.

## Safe to rerun?

- Before anything has been entered into QuickBooks: **Yes.**
- After posting the workbook and refreshing the QuickBooks exports: **Yes.**
- After posting the workbook but before refreshing QuickBooks or recording an
  override: **No.** Those payouts may be proposed again.
