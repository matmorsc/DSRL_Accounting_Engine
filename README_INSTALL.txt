DSRL ACCOUNTING ENGINE PATCH
============================

Version
-------
12 — Airbnb Adjustment-Aware Reconciliation

Install
-------
Extract the CONTENTS of this ZIP directly into the repository root.
Allow Windows to replace the four existing source files.

Files Modified
--------------
src/importers/normalize.py
src/posting/payment_allocations.py
src/posting/history.py
src/posting/airbnb_adjustments.py

Files Added
-----------
tests/test_airbnb_adjustment_aware_pipeline_v12.py
docs/AIRBNB_ADJUSTMENT_AWARE_RECONCILIATION_V12.md
README_INSTALL.txt

Validation
----------
python -m pytest tests\test_airbnb_adjustment_aware_pipeline_v12.py tests\test_airbnb_adjustment_promotion.py tests\test_airbnb_sequence.py -q

Expected: 12 passed

The existing unrelated Stripe diagnostic test may still fail in the full suite:
tests/test_stripe_seed_candidate_diagnostics_v11.py

Next Workflow
-------------
1. Rerun the main build from the raw exports so Airbnb amounts are normalized again.
2. Run: python build_airbnb_adjustment_review.py
3. Review data\processed\airbnb_adjustment_review.csv
4. Change approved_for_promotion from Pending to Yes for the four intended Airbnb groups.
5. Run: python promote_airbnb_adjustments.py
6. Type PROMOTE.
7. Rebuild downstream posting history, deposit drafts, posting package, exception reports, and workbook.
