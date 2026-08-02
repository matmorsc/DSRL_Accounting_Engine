# Phase 11A — Exception Review Data Model

Builds a review model for only the Posting Package rows marked `Needs Review`.

## Inputs
- `data/processed/posting_package_summary_v10.csv`
- `data/processed/payment_ledger_v6.csv`
- `config/posting_history.csv`
- optional manual seeds and reversal files

## Outputs
- `data/processed/exception_review_summary_v11.csv`
- `data/processed/exception_event_evidence_v11.csv`
- `data/processed/airbnb_exception_detail_v11.csv`
- `data/processed/stripe_exception_detail_v11.csv`

Run:
```powershell
python -m pytest
python build_exception_review_model_v11.py
```

No resolutions are applied and no accounting records are modified.
