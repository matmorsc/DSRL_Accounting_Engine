# QuickBooks Batch Processor Alias Fix

The QuickBooks batch engine used `processor`, while the normalized batch output
and tests use `identified_processor`.

This update makes the posting engine accept either column name.

Extract into the existing project and replace:

- `src\posting\engine.py`

New test:

- `tests\test_posting_processor_alias.py`

Run:

```powershell
python -m pytest
python run.py
```

Expected result:

- 26 passed
- Same real-data posting summary, unless the alias fix resolves additional
  batch candidates

After success:

```powershell
git add .
git commit -m "Support processor aliases in QuickBooks posting batches"
git push
```
