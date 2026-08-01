# Reconciliation Engine Update

Extract this package directly into the existing
`DSRL_Accounting_Engine` project and allow Windows to merge folders and replace
`run.py`.

The update adds:

- `src/reconciliation/engine.py`
- `tests/test_reconciliation.py`
- A refreshed `config/manual_overrides.csv` template
- Generation of `data\processed\reconciliation.csv`

Run:

```powershell
python -m pytest
python run.py
```

Expected statuses include:

- Processor Matched
- Expected Future Airbnb Payment
- Expected Future Manual Payment
- Booking.com Collection Issue
- Cash / Manual Review
- Balance Due
- No Payment Source Found
- Payment Amount Mismatch
- Refund Discrepancy
- Single Legacy Candidate
- Multiple Legacy Candidates
- Outside Reporting Scope

Manual overrides can assign:

- Approved Refund
- Reservation Modification
- Cash Received - Awaiting Deposit
- Booking.com Collection Issue
- Expected Future Manual Payment
- Expected Future Airbnb Payment
- Outside Reporting Scope
- Cancelled Reservation
- Accepted Difference

After successful tests and execution:

```powershell
git add .
git commit -m "Add reconciliation rules and manual overrides"
git push
```
