from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "src" / "presentation" / "posting_workbook.py"


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: Missing {TARGET}")
        return 1

    text = TARGET.read_text(encoding="utf-8")

    import_line = (
        "from openpyxl.worksheet.hyperlink import Hyperlink\n"
    )
    if import_line not in text:
        marker = (
            "from openpyxl.worksheet.table import "
            "Table, TableStyleInfo\n"
        )
        if marker not in text:
            print("ERROR: Could not find openpyxl import marker.")
            return 1
        text = text.replace(
            marker,
            marker + import_line,
            1,
        )

    old_dashboard = '''        open_cell.hyperlink = (
            f"#'{summary.sheet_name}'!A1"
        )
        open_cell.style = "Hyperlink"
'''
    new_dashboard = '''        open_cell.hyperlink = Hyperlink(
            ref=open_cell.coordinate,
            location=f"'{summary.sheet_name}'!A1",
            display="Open",
        )
        open_cell.style = "Hyperlink"
'''

    old_back = '''    back_cell.hyperlink = "#Dashboard!A1"
    back_cell.style = "Hyperlink"
'''
    new_back = '''    back_cell.hyperlink = Hyperlink(
        ref=back_cell.coordinate,
        location="Dashboard!A1",
        display="Back to Dashboard",
    )
    back_cell.style = "Hyperlink"
'''

    if old_dashboard not in text:
        print("ERROR: Dashboard hyperlink block was not found.")
        return 1
    if old_back not in text:
        print("ERROR: Back hyperlink block was not found.")
        return 1

    text = text.replace(old_dashboard, new_dashboard, 1)
    text = text.replace(old_back, new_back, 1)
    TARGET.write_text(text, encoding="utf-8")

    print(f"Patched {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
