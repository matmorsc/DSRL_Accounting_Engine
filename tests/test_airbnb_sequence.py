from __future__ import annotations

import pandas as pd

from src.reconciliation.airbnb_sequence import (
    assign_airbnb_payouts_by_sequence,
    summarize_airbnb_sequence_groups,
)


def test_airbnb_rows_inherit_preceding_payout():
    frame = pd.DataFrame([
        {
            "processor": "Airbnb",
            "transaction_id": "G-ONE",
            "transaction_type": "payout",
            "source_id": "G-ONE",
            "transaction_date": "2026-07-27",
            "gross_amount": 677.68,
            "net_amount": 677.68,
        },
        {
            "processor": "Airbnb",
            "transaction_id": "HM1",
            "transaction_type": "reservation",
            "source_id": "",
            "transaction_date": "2026-07-27",
            "gross_amount": 125.00,
            "net_amount": 105.62,
        },
        {
            "processor": "Airbnb",
            "transaction_id": "HM2",
            "transaction_type": "reservation",
            "source_id": "",
            "transaction_date": "2026-07-27",
            "gross_amount": 564.00,
            "net_amount": 476.58,
        },
        {
            "processor": "Airbnb",
            "transaction_id": "HM3",
            "transaction_type": "reservation",
            "source_id": "",
            "transaction_date": "2026-07-27",
            "gross_amount": 113.00,
            "net_amount": 95.48,
        },
    ])

    result, _ = assign_airbnb_payouts_by_sequence(frame)

    detail_ids = set(
        result.loc[
            result["transaction_type"].eq("reservation"),
            "source_id",
        ]
    )

    assert detail_ids == {"G-ONE"}


def test_blank_payout_gets_deterministic_id():
    frame = pd.DataFrame([
        {
            "processor": "Airbnb",
            "transaction_id": "",
            "transaction_type": "payout",
            "source_id": "",
            "transaction_date": "2026-07-17",
            "gross_amount": 68.95,
            "net_amount": 68.95,
        },
        {
            "processor": "Airbnb",
            "transaction_id": "HM1",
            "transaction_type": "reservation",
            "source_id": "",
            "transaction_date": "2026-07-17",
            "gross_amount": 81.60,
            "net_amount": 68.95,
        },
    ])

    result, _ = assign_airbnb_payouts_by_sequence(frame)

    expected = "AIRBNB-PAYOUT-20260717-01"

    assert result.loc[0, "transaction_id"] == expected
    assert result.loc[0, "source_id"] == expected
    assert result.loc[1, "source_id"] == expected


def test_sequence_summary_balances_exact_group():
    frame = pd.DataFrame([
        {
            "processor": "Airbnb",
            "transaction_id": "G-ONE",
            "transaction_type": "payout",
            "source_id": "G-ONE",
            "transaction_date": "2026-07-27",
            "gross_amount": 677.68,
            "net_amount": 677.68,
        },
        {
            "processor": "Airbnb",
            "transaction_id": "HM1",
            "transaction_type": "reservation",
            "source_id": "G-ONE",
            "transaction_date": "2026-07-27",
            "gross_amount": 125.00,
            "net_amount": 105.62,
        },
        {
            "processor": "Airbnb",
            "transaction_id": "HM2",
            "transaction_type": "reservation",
            "source_id": "G-ONE",
            "transaction_date": "2026-07-27",
            "gross_amount": 564.00,
            "net_amount": 476.58,
        },
        {
            "processor": "Airbnb",
            "transaction_id": "HM3",
            "transaction_type": "reservation",
            "source_id": "G-ONE",
            "transaction_date": "2026-07-27",
            "gross_amount": 113.00,
            "net_amount": 95.48,
        },
    ])

    summary = summarize_airbnb_sequence_groups(frame)

    assert len(summary) == 1
    assert summary.loc[0, "assigned_event_net"] == 677.68
    assert bool(summary.loc[0, "balanced"])
