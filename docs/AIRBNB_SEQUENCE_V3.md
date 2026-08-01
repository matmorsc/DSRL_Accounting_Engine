# Airbnb Sequence Pipeline V3

## Evidence from the DSRL export

The normalized Airbnb rows retain the source export order:

1. Payout row
2. One or more reservation/adjustment rows included in that payout
3. Next payout row
4. Its included detail rows

The included detail-row net amounts sum to the preceding payout amount.

Some historical payout rows have blank IDs. V3 gives those rows deterministic
internal IDs based on date and sequence.

## Safety

V3 is parallel.

It does not replace:

- `processor_transactions.csv`
- `payment_ledger.csv`
- `payout_ledger.csv`
- `posting_status.csv`
- Deposit Draft V1 or V2

## Run

```powershell
python -m pytest
python build_airbnb_sequence_v3.py
```

## Outputs

- `processor_transactions_v3.csv`
- `airbnb_sequence_diagnostics.csv`
- `airbnb_sequence_summary.csv`
- `payment_ledger_v3.csv`
- `payout_ledger_v3.csv`
- `posting_status_v3.csv`
- `payment_allocations_v3.csv`
- `payment_allocation_diagnostics_v3.csv`
- `deposit_drafts_v3.csv`
- `deposit_draft_lines_v3.csv`

Review `airbnb_sequence_summary.csv` first. Each clean group should have a zero
difference between assigned event net and payout amount.
