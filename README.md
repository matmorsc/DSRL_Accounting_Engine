# DSRL Accounting Engine

Permanent home for the Dark Sky River Lodge reconciliation and accounting system.

## Windows setup

1. Unzip this folder into Documents.
2. Open the folder in VS Code.
3. Open PowerShell in the project folder.
4. Run: `py -m venv .venv`
5. Run: `.\.venv\Scripts\Activate.ps1`
6. Run: `pip install -r requirements.txt`
7. Run: `python run.py`

## Monthly workflow

Save new exports in the matching `data/raw` folders using dated filenames.
Never overwrite or edit raw exports. Generated reports belong in `output`.

## Current next milestone

Implement V4 using structured overrides, expected-timing statuses, refund linking,
reservation modifications, pre-acquisition exclusions, and a rebuilt exception queue.
