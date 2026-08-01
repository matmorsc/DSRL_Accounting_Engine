# DSRL Accounting Pipeline

## Standard Run

From the project root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest
python run.py
```

Tests must pass before generated outputs are relied upon.

## Raw Data Folders

- `data/raw/guesty`
- `data/raw/stripe/main`
- `data/raw/stripe/cognito`
- `data/raw/stripe/keycheck`
- `data/raw/airbnb`
- `data/raw/bank`
- `data/raw/quickbooks`
- `data/raw/cognito/monthly_renewals`

Use dated filenames. Never overwrite older source exports.

## Current Processing Stages

### 1. Discovery and validation

Finds the newest source file for single-file sources and all relevant QuickBooks
files.

### 2. Normalization

Converts platform-specific exports into stable DSRL schemas.

### 3. Matching

Reservation matching priority:

1. Guesty Reservation ID
2. Channel Reservation ID
3. Legacy Stripe amount/date candidate
4. Manual override

### 4. Payout allocation

Payment events are assigned to processor payouts.

Stripe generally uses the first payout on or after the event's available date.

Airbnb grouped payouts may require additional allocation review.

### 5. Bank matching

Payouts are matched to bank deposits using processor, amount, and date tolerance.

### 6. Lifecycle reconciliation

Each reservation receives separate payment, payout, and bank statuses plus a
top-level lifecycle status.

### 7. QuickBooks posting control

QuickBooks lines are reconstructed into posting batches.

Each payout receives one of:

- Already Posted
- Unposted
- Needs Review
- Partially Posted
- Generate Entry
- Do Not Post

Only `generate_entry = Yes` may feed future draft journal entries.

## Manual Controls

### Reservation overrides

`config/manual_overrides.csv`

Used for:

- Approved Refund
- Reservation Modification
- Cash Received - Awaiting Deposit
- Booking.com Collection Issue
- Expected Future Manual Payment
- Expected Future Airbnb Payment
- Outside Reporting Scope
- Cancelled Reservation
- Accepted Difference

### Posting overrides

`config/posting_overrides.csv`

Used for:

- Already Posted
- Partially Posted
- Generate Entry
- Do Not Post
- Needs Review
