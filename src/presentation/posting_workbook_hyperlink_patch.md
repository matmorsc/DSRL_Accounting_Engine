Apply these changes to `src/presentation/posting_workbook.py`.

1. Add this import:

```python
from openpyxl.worksheet.hyperlink import Hyperlink
```

2. Replace the Dashboard hyperlink block:

```python
open_cell.hyperlink = (
    f"#'{summary.sheet_name}'!A1"
)
open_cell.style = "Hyperlink"
```

with:

```python
open_cell.hyperlink = Hyperlink(
    ref=open_cell.coordinate,
    location=f"'{summary.sheet_name}'!A1",
    display="Open",
)
open_cell.style = "Hyperlink"
```

3. Replace the payout-sheet Back to Dashboard block:

```python
back_cell.hyperlink = "#Dashboard!A1"
back_cell.style = "Hyperlink"
```

with:

```python
back_cell.hyperlink = Hyperlink(
    ref=back_cell.coordinate,
    location="Dashboard!A1",
    display="Back to Dashboard",
)
back_cell.style = "Hyperlink"
```
