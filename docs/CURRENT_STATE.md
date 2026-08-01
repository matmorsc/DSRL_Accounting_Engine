# Current Project State

## Working Capabilities

- Source discovery and validation
- Guesty normalization
- Three Stripe-account normalization
- Airbnb normalization
- Bank normalization
- QuickBooks inventory and GL normalization
- Reservation-to-processor matching
- Legacy Stripe candidate matching
- Payment ledger
- Payout ledger
- Payment-to-payout allocation
- Payout-to-bank matching
- Reservation lifecycle reconciliation
- QuickBooks posting-batch reconstruction
- QuickBooks duplicate-posting controls
- Cognito monthly-renewal normalization and legacy-payment support
- Manual reservation overrides
- Manual posting overrides
- Automated pytest suite

## Latest Known Successful State

- Full test suite passing after the QuickBooks batch wording-test correction
- Real-data pipeline completing
- Latest observed posting summary:
  - 57 Already Posted
  - 4 Needs Review
  - 63 Unposted

These figures may change when newer source exports are loaded.

## Immediate Next Milestone

Build a draft journal-entry generator that consumes only rows where:

`posting_status.csv -> generate_entry = Yes`

Before generating entries, confirm:

- revenue allocation basis,
- sales-tax liability accounts,
- Airbnb marketplace-remitted tax handling,
- Stripe and Airbnb fee-expense accounts,
- refund posting treatment,
- and whether entries should be generated per payout or per bank deposit.

## Do Not Do Yet

- Do not automatically import entries into QuickBooks.
- Do not generate entries for `Needs Review`.
- Do not treat the May 15 cutoff as conclusive evidence of posting.
- Do not attempt to generalize the engine for other businesses unless a DSRL
  requirement benefits from the abstraction.
