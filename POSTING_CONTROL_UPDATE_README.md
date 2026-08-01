# QuickBooks Posting-Control Update

Extract directly into the existing project and replace `run.py`.

New files:

- `src\importers\quickbooks.py`
- `src\posting\engine.py`
- `src\posting\__init__.py`
- `tests\test_posting.py`
- `config\posting_overrides.csv`

Before running, add this section to `config\settings.yaml`:

```yaml
quickbooks:
  assume_posted_through: 2026-05-15
  posting_date_tolerance_days: 5
  amount_tolerance: 0.02
```

Then run:

```powershell
python -m pytest
python run.py
```

Expected test count: 20 passed.

New outputs:

- `data\processed\quickbooks_gl.csv`
- `data\processed\posting_status.csv`

Posting statuses:

- Already Posted
- Unposted
- Needs Review
- Partially Posted
- Generate Entry
- Do Not Post

Only rows with `generate_entry = Yes` will later feed the journal-entry generator.

After success:

```powershell
git add .
git commit -m "Add QuickBooks posting controls and duplicate prevention"
git push
```
