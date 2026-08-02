DSRL ACCOUNTING ENGINE PATCH
============================

Phase
-----
11G — Composite Charge Allocation

Install
-------
Extract the CONTENTS of this ZIP directly into the repository root.

Files Added
-----------
promote_composite_charge_allocation_v11.py
src/review/composite_charge_allocation.py
tests/test_composite_charge_allocation_v11.py
config/composite_charge_allocations_v11.csv
config/composite_charge_approvals_v11.csv
docs/COMPOSITE_CHARGE_ALLOCATION_V11_PHASE_11G.md
README_INSTALL.txt

Files Modified
--------------
None

Files Deleted
-------------
None

Run
---
python -m pytest
python promote_composite_charge_allocation_v11.py

Then approve the wedding-party row in:

config/composite_charge_approvals_v11.csv

Preview and apply:

python promote_composite_charge_allocation_v11.py
python promote_composite_charge_allocation_v11.py --apply
