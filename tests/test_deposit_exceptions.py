from __future__ import annotations

import pandas as pd

from src.reports.deposit_exceptions import (
    build_deposit_exception_review,
)


def test_ready_balanced_draft_is_excluded():
    drafts = pd.DataFrame([{
        "payout_id": "po1",
        "processor": "Stripe",
        "deposit_date": "2026-06-01",
        "bank_amount": 100.0,
        "draft_total": 100.0,
        "difference": 0.0,
        "balanced": "Yes",
        "draft_status": "Ready for Review",
        "review_reason": "",
    }])

    result = build_deposit_exception_review(
        deposit_drafts=drafts,
        draft_lines=pd.DataFrame(
            columns=["payout_id"]
        ),
        allocation_diagnostics=pd.DataFrame(
            columns=[
                "payout_id",
                "diagnostic_type",
            ]
        ),
        payout_ledger=pd.DataFrame(
            columns=["payout_id"]
        ),
        payment_ledger=pd.DataFrame(
            columns=[
                "payout_id",
                "payment_event_id",
            ]
        ),
    )

    assert result.empty


def test_unlinked_event_is_classified():
    drafts = pd.DataFrame([{
        "payout_id": "po1",
        "processor": "Stripe",
        "deposit_date": "2026-06-01",
        "bank_amount": 100.0,
        "draft_total": 0.0,
        "difference": -100.0,
        "balanced": "No",
        "draft_status": "Review Required",
        "review_reason": "Missing events.",
    }])

    diagnostics = pd.DataFrame([{
        "payout_id": "po1",
        "diagnostic_type": "Unlinked Payment Event",
    }])

    result = build_deposit_exception_review(
        deposit_drafts=drafts,
        draft_lines=pd.DataFrame(
            columns=["payout_id"]
        ),
        allocation_diagnostics=diagnostics,
        payout_ledger=pd.DataFrame([{
            "payout_id": "po1",
            "allocation_status": "Difference",
            "allocation_difference": -100.0,
            "bank_match_status": "Matched",
        }]),
        payment_ledger=pd.DataFrame([{
            "payout_id": "po1",
            "payment_event_id": "evt1",
        }]),
    )

    assert (
        result.loc[0, "primary_issue"]
        == "No allocated draft lines"
    )
