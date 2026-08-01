# DSRL Phase 10B — openpyxl Fix

The prior workbook code depended on `artifact_tool`, which is not installed in
the project's virtual environment.

This patch replaces it with `openpyxl`.

## Extract and install

Extract into the project, then run:

```powershell
python -m pip install openpyxl
```

Add this to `requirements.txt` if the file exists:

```text
openpyxl>=3.1.5
```

A convenience file is included:

`requirements_v10_additions.txt`

## Run

```powershell
python -m pytest
python build_quickbooks_posting_package_v10.py
```

Expected output:

`output\QuickBooks_Posting_Package_YYYY-MM.xlsx`

No QuickBooks transactions are created.
