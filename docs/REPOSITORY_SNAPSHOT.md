# Repository Snapshot

Generated: 2026-08-01T11:58:27-06:00

## Branch and Status

```text
## main...origin/main
?? .github/
?? CONTINUITY_UPDATE_README.md
?? docs/ACCOUNTING_RULES.md
?? docs/ARCHITECTURE.md
?? docs/CHANGELOG.md
?? docs/CURRENT_STATE.md
?? docs/DATA_DICTIONARY.md
?? docs/HANDOFF.md
?? docs/PIPELINE.md
?? docs/ROADMAP.md
?? scripts/
```

## Recent Commits

```text
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
.gitignore
LIFECYCLE_TEST_FIX_README.md
LIFECYCLE_UPDATE_README.md
MATCHING_UPDATE_README.md
NORMALIZATION_UPDATE_README.md
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
config/manual_overrides.csv
config/posting_overrides.csv
config/settings.yaml
data/processed/.gitkeep
docs/DSRL_Accounting_Engine_Specification_v1.docx
docs/DSRL_Master_Reconciliation_v3_reviewed.xlsx
docs/PROJECT_STATE.md
output/.gitkeep
pytest.ini
requirements.txt
run.py
run_engine.bat
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
src/models/__init__.py
src/posting/__init__.py
src/posting/batches.py
src/posting/engine.py
src/reconciliation/__init__.py
src/reconciliation/engine.py
src/reconciliation/payouts.py
src/reports/__init__.py
src/reports/inventory.py
src/rules/__init__.py
src/rules/status.py
tests/test_lifecycle.py
tests/test_matching.py
tests/test_payouts.py
tests/test_posting.py
tests/test_posting_batch_date_alias.py
tests/test_posting_dates.py
tests/test_posting_processor_alias.py
tests/test_qb_batches_cognito.py
tests/test_reconciliation.py
```

## Test Command

```powershell
python -m pytest
```

## Pipeline Command

```powershell
python run.py
```
