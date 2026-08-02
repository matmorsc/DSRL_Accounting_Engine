# Phase 11D — Stripe Seed Promotion

Merge this package into the project root.

Then edit `config/stripe_seed_approvals_v11.csv` and mark only Paul Weissmann and Randal Jewell as `Approved`.

Run:

```powershell
python -m pytest
python promote_stripe_seed_candidates_v11.py
```

After reviewing the preview:

```powershell
python promote_stripe_seed_candidates_v11.py --apply
```
