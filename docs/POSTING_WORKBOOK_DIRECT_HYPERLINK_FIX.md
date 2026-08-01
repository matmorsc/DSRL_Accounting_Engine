# Direct Internal Hyperlink Fix

The earlier patch script relied on matching an exact source-code block and
failed against the installed renderer.

This update directly replaces:

`src/presentation/posting_workbook.py`

Internal workbook links are now created with explicit hyperlink `location`
values and no external relationship target.

The test now finds the dynamic "Back to Dashboard" cell by its displayed text
instead of assuming a fixed row.

Run:

```powershell
python -m pytest
python build_quickbooks_posting_package_v10.py
```

Do not run the obsolete `patch_posting_workbook_hyperlinks.py` script.
