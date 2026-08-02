# Phase 11D — Stripe Seed Approval and Promotion

1. Open `config/stripe_seed_approvals_v11.csv`.
2. Change only Paul Weissmann and Randal Jewell from `Pending` to `Approved`.
3. Run preview:

```powershell
python -m pytest
python promote_stripe_seed_candidates_v11.py
```

4. Confirm both rows show `Ready to Promote` in `data/processed/stripe_seed_promotion_preview_v11.csv`.
5. Apply:

```powershell
python promote_stripe_seed_candidates_v11.py --apply
```

The script revalidates eligibility, sign safety, exact tie-out, line counts, totals, and duplicates before appending to `config/posting_history_manual_seeds.csv`.

Then rebuild:

```powershell
python build_posting_history_reversals_v8.py
python build_ledger_deposit_drafts_v9.py
python build_posting_package_v10.py
python build_exception_review_model_v11.py
python build_exception_reconciliation_v11.py
python build_quickbooks_posting_package_v10.py
```
