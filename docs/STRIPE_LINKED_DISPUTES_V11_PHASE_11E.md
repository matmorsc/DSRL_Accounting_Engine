# Phase 11E — Linked Stripe Disputes

## Why the treatment changed

The `$110.00` Stripe dispute was identified online as belonging to Paul
Weissmann. Paul already has active Original posting history.

Therefore the dispute is not posted to a generic refund account. Instead:

- reverse Paul's original revenue allocation;
- do not reverse the original Stripe processing fee;
- add the new dispute fee as a Source Event;
- preserve `reversal_of_posting_line_id`.

## Current case

- Reservation ID: `6a31ea3820bb4b0013d22b90`
- Guest: `Paul Weissmann`
- Dispute gross: `-95.00`
- Dispute fee: `-15.00`
- Net payout effect: `-110.00`

## Workflow

Run:

```powershell
python -m pytest
python promote_stripe_dispute_events_v11.py
```

Open:

`config/stripe_dispute_approvals_v11.csv`

For the eligible row, enter:

```text
linked_reservation_id = 6a31ea3820bb4b0013d22b90
linked_guest = Paul Weissmann
approval_status = Approved
```

Preview:

```powershell
python promote_stripe_dispute_events_v11.py
```

Expected:

- reversal total `-95.00`;
- dispute fee `-15.00`;
- proposed total `-110.00`;
- status `Ready to Promote`.

Apply:

```powershell
python promote_stripe_dispute_events_v11.py --apply
```
