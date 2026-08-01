from __future__ import annotations

from pathlib import Path


SOURCE_FOLDERS = {
    "Guesty": ("data/raw/guesty", False),
    "Stripe Main": ("data/raw/stripe/main", False),
    "Stripe Cognito": ("data/raw/stripe/cognito", False),
    "Stripe Keycheck": ("data/raw/stripe/keycheck", False),
    "Airbnb": ("data/raw/airbnb", False),
    "Bank": ("data/raw/bank", False),
    "QuickBooks": ("data/raw/quickbooks", True),
}

ALLOWED_SUFFIXES = {".csv", ".xlsx", ".xls"}


def _data_files(folder: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in folder.iterdir()
            if path.is_file()
            and path.name.lower() != "readme.md"
            and path.suffix.lower() in ALLOWED_SUFFIXES
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def discover_sources(root: Path) -> dict[str, list[Path]]:
    sources: dict[str, list[Path]] = {}
    errors: list[str] = []

    for source_name, (relative_folder, allow_multiple) in SOURCE_FOLDERS.items():
        folder = root / relative_folder

        if not folder.exists():
            errors.append(f"{source_name}: missing folder {folder}")
            continue

        files = _data_files(folder)

        if not files:
            errors.append(f"{source_name}: no source files found in {folder}")
            continue

        sources[source_name] = files if allow_multiple else [files[0]]

    if errors:
        raise FileNotFoundError("; ".join(errors))

    return sources
