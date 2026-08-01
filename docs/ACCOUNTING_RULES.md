# DSRL Accounting Rules

## Revenue Classification

Property class is derived from listing:

- RV listing -> RV
- Cabin or A-frame listing -> Cabin
- all other lodging listings -> Motel

Income account is based on property class and stay length.

## Airbnb

- Match using Guesty Channel Reservation ID and Airbnb confirmation code.
- Future stays without a payout may be expected, not exceptions.
- Airbnb host payout must not be compared directly with guest-facing total
  without considering Airbnb fees, refunds, modifications, and Airbnb-remitted tax.
- Airbnb-remitted tax must not be remitted again by DSRL.

## Booking.com

Historical treatment changed over time.

Before July 2026, Booking.com reservations were generally charged through the
Guesty-connected Stripe workflow.

A past-due Booking.com reservation with no processor match is a
`Booking.com Collection Issue`, not a generic missing-payment exception.

Tax treatment must be established independently from payment collection.

## Cash and Check

Cash and checks have separate stages:

- expected,
- received,
- awaiting deposit,
- deposited,
- posted.

Cash received but not deposited is not missing revenue. It is an operational
cash-control item.

## Refunds and Modifications

Refunds and reservation modifications are business events.

They must be linked to the reservation and should not automatically appear as
generic payment mismatches.

## Pre-acquisition Activity

Reservations ending before the acquisition date are outside current reporting
scope unless intentionally included for historical analysis.

Current configured acquisition date:

- October 1, 2025

## QuickBooks Duplicate Prevention

A payout is eligible for a generated entry only when:

- it has reached the bank,
- it is not matched to an existing QuickBooks line or posting batch,
- it is after the assumed-posted cutoff or manually approved,
- and `generate_entry = Yes`.

Current assumed-posted cutoff:

- May 15, 2026

The cutoff is a control, not proof. Actual QuickBooks matching takes precedence.

## Fully Reconciled

A reservation is fully reconciled only when:

1. It is valid and in scope.
2. Payment activity is resolved.
3. Refunds and modifications are explained.
4. Payment activity is allocated to a payout.
5. The payout is matched to the bank.
6. Income account and class are assigned.
7. QuickBooks posting status is known.
8. Tax responsibility is known.
9. No unresolved exception remains.
