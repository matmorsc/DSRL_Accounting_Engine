# V8 Phase B Posting-Group Fix

Airbnb can emit a reservation and a later adjustment with the same confirmation
code. The existing normalized `payment_event_id` therefore may not be unique.

Phase A already creates separate deterministic `posting_group_id` values because
the reservation and adjustment differ by payout and event metadata.

Phase B previously regrouped proposals by `payment_event_id`, accidentally
combining the two groups again.

This patch:

- reviews one row per `posting_group_id`,
- uniquely resolves the corresponding payment-ledger row using transaction
  type, payout, transaction ID, and date,
- approves and promotes by `posting_group_id`,
- keeps Source Event groups excluded for Phase C,
- and does not alter existing promoted history.
