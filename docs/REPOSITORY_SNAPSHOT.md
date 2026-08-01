# Repository Snapshot

Generated: 2026-08-01T12:47:28-06:00

## Branch and Status

```text
## main...origin/main
```

## Recent Commits

```text
4f8e601 Add payment allocation, Airbnb sequence grouping, and deposit draft V3
7ce9314 Add read-only QuickBooks deposit draft generator
7100dc4 Add project continuity documentation and automated tests
d69a20f Relax combined payout status wording test
f066e47 Handle missing payout dates in posting controls
a35be1e Update reconciliation tests for lifecycle ledgers
1a8b03f Add payout allocation and bank reconciliation
cfb4c40 Add reconciliation rules and manual overrides
192d318 Add reservation to processor matching engine
7e83d03 Add normalization layer and standardized data model
b04d230 Add source file discovery and validation
a5df278 Initial DSRL Accounting Engine setup
```

## Tracked Project Files

```text
.github/workflows/tests.yml
.gitignore
AIRBNB_SEQUENCE_V3_README.md
AIRBNB_UNLINKED_UPDATE_README.md
CONTINUITY_UPDATE_README.md
DEPOSIT_DRAFT_UPDATE_README.md
LIFECYCLE_TEST_FIX_README.md
LIFECYCLE_UPDATE_README.md
MATCHING_UPDATE_README.md
NORMALIZATION_UPDATE_README.md
PAYMENT_ALLOCATION_UPDATE_README.md
PAYOUT_BANK_UPDATE_README.md
POSTING_CONTROL_UPDATE_README.md
POSTING_DATE_FIX_README.md
QB_BATCH_COGNITO_UPDATE_README.md
QB_BATCH_DATE_ALIAS_FIX_README.md
QB_BATCH_PROCESSOR_ALIAS_FIX_README.md
QB_BATCH_TEST_FIX_README.md
README.md
RECONCILIATION_UPDATE_README.md
SETTINGS_PATCH.txt
UNLINKED_BLANK_ID_FIX_README.md
build_airbnb_sequence_v3.py
build_deposit_drafts.py
build_deposit_drafts_v2.py
build_unlinked_stripe_review.py
config/deposit_draft_rules.yaml
config/manual_overrides.csv
config/posting_overrides.csv
config/settings.yaml
data/processed/.gitkeep
docs/ACCOUNTING_RULES.md
docs/AIRBNB_AND_UNLINKED_REVIEW.md
docs/AIRBNB_SEQUENCE_V3.md
docs/ARCHITECTURE.md
docs/CHANGELOG.md
docs/CURRENT_STATE.md
docs/DATA_DICTIONARY.md
docs/DEPOSIT_DRAFTS.md
docs/DSRL_Accounting_Engine_Specification_v1.docx
docs/DSRL_Master_Reconciliation_v3_reviewed.xlsx
docs/HANDOFF.md
docs/PAYMENT_ALLOCATIONS.md
docs/PIPELINE.md
docs/PROJECT_STATE.md
docs/REPOSITORY_SNAPSHOT.md
docs/ROADMAP.md
output/.gitkeep
pytest.ini
requirements.txt
run.py
run_engine.bat
scripts/create_repository_snapshot.py
src/__init__.py
src/importers/__init__.py
src/importers/cognito.py
src/importers/discovery.py
src/importers/guesty.py
src/importers/normalize.py
src/importers/quickbooks.py
src/matching/__init__.py
src/matching/engine.py
src/matching/legacy.py
src/matching/unlinked_review.py
src/models/__init__.py
src/posting/__init__.py
src/posting/batches.py
src/posting/deposit_drafts.py
src/posting/deposit_drafts_v2.py
src/posting/engine.py
src/posting/payment_allocations.py
src/reconciliation/__init__.py
src/reconciliation/airbnb_sequence.py
src/reconciliation/engine.py
src/reconciliation/payouts.py
src/reports/__init__.py
src/reports/inventory.py
src/rules/__init__.py
src/rules/status.py
tests/test_airbnb_sequence.py
tests/test_airbnb_unlinked.py
tests/test_deposit_drafts.py
tests/test_lifecycle.py
tests/test_matching.py
tests/test_payment_allocations.py
tests/test_payouts.py
tests/test_posting.py
tests/test_posting_batch_date_alias.py
tests/test_posting_dates.py
tests/test_posting_processor_alias.py
tests/test_qb_batches_cognito.py
tests/test_reconciliation.py
tests/test_unlinked_blank_ids.py
```

## Test Command

```powershell
python -m pytest
```

## Pipeline Command

```powershell
python run.py
```
