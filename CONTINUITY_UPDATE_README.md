# DSRL Continuity Update

This update makes the repository—not the chat—the durable project memory.

Extract directly into the existing project. It adds documentation, a repository
snapshot script, and GitHub Actions testing.

## Added documentation

- `docs/ARCHITECTURE.md`
- `docs/PIPELINE.md`
- `docs/ACCOUNTING_RULES.md`
- `docs/DATA_DICTIONARY.md`
- `docs/CURRENT_STATE.md`
- `docs/HANDOFF.md`
- `docs/ROADMAP.md`
- `docs/CHANGELOG.md`

## Added tools

- `scripts/create_repository_snapshot.py`
- `.github/workflows/tests.yml`

## Run locally

```powershell
python .\scripts\create_repository_snapshot.py
python -m pytest
```

Review the generated:

`docs\REPOSITORY_SNAPSHOT.md`

Then commit:

```powershell
git add .
git commit -m "Add project continuity documentation and automated tests"
git push
```

GitHub Actions should automatically run the test suite after the push.

## Starting a future chat

Upload or paste `docs/HANDOFF.md` and `docs/CURRENT_STATE.md`, or point the new
conversation to the repository and ask it to begin by reading those files.
