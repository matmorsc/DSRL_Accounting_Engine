# DSRL Airbnb Sequence Pipeline V3

This update uses the actual row order of the Airbnb transaction export rather
than guessing a payout-reference column.

It is a parallel comparison pipeline and does not overwrite V1 or V2.

## Extract

Extract directly into the existing project.

## Run

```powershell
python -m pytest
python build_airbnb_sequence_v3.py
```

The test count should increase by three.

## Upload after running

- `data\processed\airbnb_sequence_summary.csv`
- `data\processed\deposit_drafts_v3.csv`
- `data\processed\payment_allocation_diagnostics_v3.csv`

## Do not commit as the primary pipeline yet

Commit only after the V3 results prove materially better than V2.
