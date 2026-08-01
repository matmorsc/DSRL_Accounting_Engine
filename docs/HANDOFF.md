# New Chat / Developer Handoff

Use this file when starting a new ChatGPT conversation or handing the project to
another developer.

## Project

Private DSRL accounting and reconciliation engine for Dark Sky River Lodge.

GitHub repository:

`https://github.com/matmorsc/DSRL_Accounting_Engine`

## First Instructions

1. Read:
   - `docs/CURRENT_STATE.md`
   - `docs/ARCHITECTURE.md`
   - `docs/ACCOUNTING_RULES.md`
   - `docs/PIPELINE.md`
   - `docs/DATA_DICTIONARY.md`
   - `docs/ROADMAP.md`
2. Inspect recent Git commits.
3. Run:
   - `python -m pytest`
   - `python run.py`
4. Do not propose rebuilding the project from scratch.
5. Preserve DSRL-specific behavior unless Matt explicitly changes it.
6. Do not generate journal entries for payouts that may already be posted.
7. Treat repository code, tests, configuration, and documentation as the source
   of truth over remembered chat context.

## Current Objective

Build safe draft journal entries for confirmed unposted payouts, then build the
sales-tax ledger and reporting worksheet.

## User Priorities

- This is a tool for Matt's use at DSRL.
- Reliability and auditability matter more than broad applicability.
- Avoid duplicate QuickBooks postings.
- Keep instructions concrete and step-by-step.
- Prefer small tested milestones.
