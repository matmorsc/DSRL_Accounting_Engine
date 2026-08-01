# Phase 10B — openpyxl Workbook Renderer

The original Phase 10B renderer incorrectly depended on `artifact_tool`, which
is available in the development environment but is not a normal dependency in
the DSRL project.

The workbook renderer now uses `openpyxl`.

## Install

```powershell
python -m pip install openpyxl
```

Also add this line to the project's dependency file:

```text
openpyxl>=3.1.5
```

## Run

```powershell
python -m pytest
python build_quickbooks_posting_package_v10.py
```

## Output

`output/QuickBooks_Posting_Package_YYYY-MM.xlsx`

No QuickBooks transactions are created.
