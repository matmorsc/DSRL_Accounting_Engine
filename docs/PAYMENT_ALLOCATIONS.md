# Payment-Event Allocation Layer

## Why this exists

Deposit Draft V1 used reservation totals as the allocation basis. That approach
worked for simple full-payment reservations but produced large differences for
partial payments, multiple charges, modifications, and grouped payouts.

V2 starts with the actual payment event.

The payment event determines the dollar amount.

The linked reservation determines:

- income account,
- QuickBooks class,
- and direct-tax composition.

## Direct Stripe events

For a direct Stripe charge:

1. Take the actual Stripe gross event amount.
2. Allocate that gross amount across reservation revenue and direct taxes using
   the reservation's revenue/tax composition.
3. Force rounding to equal the payment event exactly.
4. Record the Stripe fee as a negative deposit line.

## Airbnb events

For Airbnb:

1. Use the Airbnb event gross amount as lodging revenue.
2. Exclude Airbnb-remitted marketplace tax.
3. Record the Airbnb fee only when its QuickBooks account is configured.

## Safety

V2 does not overwrite V1 files.

It produces:

- `payment_allocations.csv`
- `payment_allocation_diagnostics.csv`
- `deposit_drafts_v2.csv`
- `deposit_draft_lines_v2.csv`

This lets the two approaches be compared before any older logic is removed.
