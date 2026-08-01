# V6 Stripe metadata inheritance fix

V6 correctly joined 154 Stripe balance transactions to their authoritative
payout IDs, but refund and adjustment rows still lacked reservation metadata.

This patch calls `inherit_stripe_source_metadata()` before payment allocation.
That lets refund and adjustment rows inherit reservation ID, guest, and listing
from the original charge sharing the same Stripe Source.

No payout-assignment or accounting rule is changed.

Run:

```powershell
python -m pytest
python build_stripe_payout_reconciliation_v6.py
```

Expected known payout:

`po_1TqjcpJtejknM735RBYtfOau`

- Bank amount: 134.32
- Draft total: 134.32
- Difference: 0.00
- Balanced: Yes
