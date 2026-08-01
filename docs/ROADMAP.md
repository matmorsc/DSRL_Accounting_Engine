# DSRL Accounting Engine Roadmap

## Completed

- Project setup and GitHub backup
- Raw-data archive structure
- Source validation
- Normalized ledgers
- Reservation matching
- Payment-to-payout allocation
- Bank reconciliation
- Lifecycle statuses
- QuickBooks posting control
- Cognito monthly-renewal support
- Automated tests

## Milestone 1: Draft Journal Entries

Goals:

- Generate entries only for `generate_entry = Yes`.
- Produce balanced entries.
- Allocate revenue by income account and class.
- Separate processor fees.
- Separate DSRL-collected tax liabilities.
- Exclude marketplace-remitted taxes.
- Preserve reservation and payout audit references.
- Output a reviewable CSV before any QuickBooks import format.

## Milestone 2: Posting Review Workbook

Goals:

- Dashboard
- Journal-entry review
- Posting-status review
- Reservation audit trail
- Exceptions
- Overrides
- Source inventory

## Milestone 3: Sales-Tax Ledger

Goals:

- Normalize inconsistent tax labels.
- Identify DSRL-collected versus marketplace-collected tax.
- Assign cash-receipt dates.
- Generate reporting-period summaries.
- Prevent duplicate marketplace-tax remittance.

## Milestone 4: QuickBooks Import

Goals:

- Choose the safest supported import format.
- Generate import files only from approved draft entries.
- Track imported versus not imported.
- Preserve reversal and correction history.

## Milestone 5: Monthly Close

Goals:

- One command to validate inputs and create all outputs.
- Clear close checklist.
- Review queue limited to genuine exceptions.
- Archive each completed accounting period.
