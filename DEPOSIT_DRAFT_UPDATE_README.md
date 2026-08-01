# DSRL Deposit Draft Generator Update

This is a standalone, read-only milestone. It does not replace `run.py`.

Extract directly into the existing project.

## Added

- `build_deposit_drafts.py`
- `src/posting/deposit_drafts.py`
- `config/deposit_draft_rules.yaml`
- `tests/test_deposit_drafts.py`
- `docs/DEPOSIT_DRAFTS.md`

## Run tests

```powershell
python -m pytest
```

The total test count should increase by four.

## Generate drafts

First refresh the existing pipeline:

```powershell
python run.py
```

Then generate the deposit drafts:

```powershell
python build_deposit_drafts.py
```

New outputs:

- `data\processed\deposit_drafts.csv`
- `data\processed\deposit_draft_lines.csv`

No QuickBooks transactions are created.

## Review configuration first

Open:

`config\deposit_draft_rules.yaml`

The Stripe account and DSRL class mappings are prefilled from the workflow shown
in QuickBooks.

The Airbnb fee account is intentionally blank until its exact QuickBooks account
name is confirmed.

## Commit after a successful run

```powershell
git add .
git commit -m "Add read-only QuickBooks deposit draft generator"
git push
```
