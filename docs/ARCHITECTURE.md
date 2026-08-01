# DSRL Accounting Engine Architecture

## Purpose

The DSRL Accounting Engine is a private operating tool for Dark Sky River Lodge.

Its job is to turn exports from Guesty, Stripe, Airbnb, Cognito, the bank, and
QuickBooks into a repeatable accounting workflow that:

- explains each reservation and payment,
- connects payments to processor payouts,
- connects payouts to bank deposits,
- prevents duplicate QuickBooks postings,
- supports revenue allocation by class and income account,
- supports sales-tax reporting,
- and produces a review queue for genuine exceptions.

This project is not currently intended to support other businesses. DSRL-specific
rules should be explicit and easy to change rather than hidden inside generic
abstractions.

## Source of Truth

The repository is the durable source of truth.

The chat is useful for design and implementation, but the project must remain
understandable from:

- source code,
- configuration,
- tests,
- documentation,
- raw-data folder conventions,
- and Git history.

## Pipeline

1. Source discovery
2. Validation
3. Normalization
4. Reservation-to-payment matching
5. Payment-to-payout allocation
6. Payout-to-bank matching
7. Reservation lifecycle reconciliation
8. QuickBooks posting control
9. Draft journal entries
10. Sales-tax reporting
11. Management reporting

Each stage should consume normalized outputs from the prior stage and should not
silently modify raw source data.

## Main Source Systems

### Guesty

Operational source of truth for reservations.

Important identifiers:

- Guesty Reservation ID
- Channel Reservation ID

Important fields:

- booking source,
- payment method,
- confirmation date,
- check-in and check-out,
- listing,
- accommodation revenue,
- taxes,
- total paid,
- total refunded,
- and balance due.

### Stripe

Three accounts are currently relevant:

- Main Guesty
- Legacy Cognito
- Legacy Keycheck

The main account usually contains Guesty reservation metadata. Legacy accounts
often require amount/date candidates or Cognito support.

### Airbnb

Airbnb confirmation codes match Guesty Channel Reservation IDs.

Airbnb reservation activity, host payouts, service fees, and marketplace-remitted
tax must remain separate concepts.

### Cognito

Cognito monthly-renewal submissions support historical monthly-guest payment
identification, particularly for legacy Stripe activity.

### Bank

The bank export confirms actual cash movement.

### QuickBooks

QuickBooks is the accounting destination and a historical validation source.
It must not be assumed to be complete.

Existing postings are detected before journal entries are generated.

## Core Ledgers

- `reservations.csv`
- `processor_transactions.csv`
- `payment_ledger.csv`
- `payout_ledger.csv`
- `bank_transactions.csv`
- `matches.csv`
- `reconciliation.csv`
- `quickbooks_gl.csv`
- `quickbooks_posting_batches.csv`
- `posting_status.csv`

Generated data belongs in `data/processed` and is not committed.

## Accounting Dimensions

### QuickBooks Classes

- RV
- Motel
- Cabin

### Income Accounts

- Cabin Rent - Monthly
- Cabin Rent - Short-Term
- Cancellations
- Coupon Code
- Motel Rent - Monthly
- Motel Rent - Short Term
- Refunds
- RV Rent - Monthly
- RV Rent - Nightly

### Monthly Rule

The current configurable rule is:

- 28 nights or more: Monthly
- fewer than 28 nights: Short-Term or Nightly

## Safety Principles

- Never force an uncertain legacy match.
- Never generate a journal entry for a payout classified as already posted.
- Never alter raw exports.
- Preserve manual decisions in override files.
- Treat expected timing differences separately from accounting errors.
- A processor match alone does not mean fully reconciled.
- All new accounting logic must have tests.
