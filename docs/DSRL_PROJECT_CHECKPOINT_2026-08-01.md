# DSRL Accounting Engine — Project Checkpoint

**Checkpoint date:** 2026-08-01
**Next milestone:** V8 Posting History, Phase A

## Current working result

- Airbnb sequence grouping is promoted and working: 33 of 37 groups balanced.
- Latest deposit-draft validation: 51 ready / 12 review; 51 balanced / 12 unbalanced.
- Stripe itemized payout reconciliation report is authoritative and works:
  - 154 payout-membership rows imported.
  - 154 payment events matched exactly.
  - 5 date-based payout assignments corrected.
- Exact Stripe payout assignment is **not** the remaining problem.

## Known unresolved Stripe case

- Payout: `po_1TqjcpJtejknM735RBYtfOau`
- Bank amount: `134.32`
- Incorrect draft: `188.64`
- Difference: `54.32`
- Correct components:
  - Charge net `+91.56`
  - Charge net `+97.08`
  - Refund `-54.54`
  - Application-fee adjustment `+0.22`
  - Total `134.32`
- Original charge source: `ch_3ToU7JJtejknM7351lfydf5x`
- Original charge transaction: `txn_3ToU7JJtejknM7351Ihb23yD`
- Original charge metadata: Dan Calabro / DSRL RV 8 / gross `109.09` / fee `3.90` / net `105.19`.
- Guesty reservation ID `6a456ec82f304185394fbbca` is no longer present in the current reservations export.

## Root cause

The engine still treats allocations as temporary calculations. Refunds try to rediscover accounting classification from the current Guesty export. That is unreliable for historical reservations.

## Architectural decision

Create a permanent CSV-backed `posting_history.csv`. Each charge's approved accounting lines become durable accounting truth. Refunds, disputes, reversals, and adjustments reuse or reverse those original lines using Stripe `Source`.

No SQL. No database. Persistent state remains in Git-trackable CSV files.

## Do not do next

- Do not add another date or residual heuristic.
- Do not create a manual payout adjustment for the `54.32` difference.
- Do not promote V4/V5 experimental charge-family or residual-bundle logic.
- Do not modify the primary pipeline before parallel V8 validation succeeds.

## Next implementation step

Build **V8 Phase A only**:

1. Add `config/posting_history.csv` with the schema in `DSRL_Posting_History_Architecture_Specification_V8.docx`.
2. Add a posting-history generator that translates classifiable payment events into proposed lines.
3. Write `data/processed/posting_history_proposed.csv`; do not overwrite persistent history.
4. Add deterministic IDs and duplicate-prevention tests.
5. Add reversal-line tests using the known Stripe case.
6. Keep V8 parallel and read-only.

## First commands when resuming

```powershell
git status
python -m pytest
```

Then open the V8 architecture specification and implement Phase A.
