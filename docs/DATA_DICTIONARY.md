# DSRL Data Dictionary

## Reservation Identifiers

- `reconciliation_id`: Internal DSRL identifier for one reservation row.
- `reservation_id`: Guesty internal reservation ID.
- `channel_reservation_id`: Airbnb, Booking.com, or other channel identifier.

## Payment Fields

- `gross_amount`: Customer or channel payment-event amount before processor fees.
- `processor_fee`: Fee charged by the payment processor or channel.
- `net_amount`: Amount remaining after the event-level processor fee.
- `transaction_type`: Charge, payment, reservation, refund, payout, or adjustment.
- `payment_event_id`: Stable internal identifier combining processor account and transaction ID.

## Payout Fields

- `payout_id`: Processor payout identifier.
- `payout_amount`: Cash amount sent by the processor.
- `allocation_status`: Whether assigned payment-event net totals explain the payout.
- `bank_match_status`: Whether the payout is matched to a bank deposit.

## Reconciliation Fields

- `payment_status`: Reservation-level payment interpretation.
- `payout_status`: Reservation-level payout interpretation.
- `bank_status`: Reservation-level deposit interpretation.
- `lifecycle_status`: Top-level summary of the reservation's current stage.
- `review_required`: Whether a human decision is currently required.

## Posting Fields

- `quickbooks_batch_id`: Internal identifier for reconstructed QuickBooks posting activity.
- `posting_status`: Already Posted, Unposted, Needs Review, Partially Posted,
  Generate Entry, or Do Not Post.
- `generate_entry`: The hard gate for future journal-entry generation.
