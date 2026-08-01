# DSRL Direct Internal Hyperlink Fix

Extract this update directly into the project folder.

It replaces:

- `src/presentation/posting_workbook.py`
- `tests/test_internal_hyperlinks_v10.py`

Do not run:

```powershell
python patch_posting_workbook_hyperlinks.py
```

That obsolete patch script can be deleted.

Run:

```powershell
python -m pytest
python build_quickbooks_posting_package_v10.py
```

Then reopen the regenerated workbook. The navigation links should work without
Excel reporting repaired XML records.
