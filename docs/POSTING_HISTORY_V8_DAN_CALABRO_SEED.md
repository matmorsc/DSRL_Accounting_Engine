# V8 Phase C — Dan Calabro Manual Seed

The missing original charge is seeded from documented Stripe evidence.

## Original charge

- Stripe Source: `ch_3ToU7JJtejknM7351lfydf5x`
- Guest: Dan Calabro
- Listing: DSRL RV 8
- Gross: 109.09
- Stripe fee: 3.90
- Net: 105.19

## Original posting lines

- RV Rent - Nightly: 103.50
- State lodging tax: 3.00
- County lodging tax: 2.59
- Stripe processing fee: -3.90

The positive lines total 109.09.
All four lines total 105.19.

## Reversal acceptance test

Phase C should generate:

- refund reversal: -54.54
- fee adjustment reversal: +0.22
- net effect: -54.32

The seed is read alongside persistent posting history for preview generation.
It does not modify `config/posting_history.csv`.
