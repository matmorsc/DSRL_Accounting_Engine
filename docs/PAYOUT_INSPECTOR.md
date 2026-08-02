# Payout Inspector

## Purpose

`inspect_payout.py` consolidates all available evidence for one payout ID.

It is read-only. It does not modify configuration, posting history, processed
data, or QuickBooks.

## Usage

```powershell
python inspect_payout.py po_1TtGgMJtejknM735PQ0D9nCF
```

Save the report:

```powershell
python inspect_payout.py po_1TtGgMJtejknM735PQ0D9nCF --save
```

The saved report is written to:

`output/payout_inspection_<payout_id>.txt`

## Evidence displayed

- payout amount and package difference;
- bank match and confidence;
- payment events;
- active persistent/manual-seed posting history;
- reversal-preview lines;
- Stripe source-family reconciliation;
- reservation evidence;
- current exception recommendation and safety status.

## Recommended investigation order

```powershell
python inspect_payout.py po_1TtGgMJtejknM735PQ0D9nCF --save
python inspect_payout.py po_1Tov4YJtejknM735veeJbp36 --save
```
