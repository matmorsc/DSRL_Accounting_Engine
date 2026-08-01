from __future__ import annotations

import pandas as pd

from src.reconciliation.stripe_refund_bundles import (
    build_refund_bundles,
    inherit_stripe_source_metadata,
    reassign_refund_bundles_by_residual,
)


def ledger():
    rows = [
        {
            "payment_event_id": "Main::charge_old",
            "processor": "Stripe",
            "processor_account": "Main",
            "transaction_id": "charge_old",
            "transaction_type": "charge",
            "source_id": "ch_1",
            "transaction_date": "2026-07-01 00:00:00",
            "available_date": "2026-07-03 00:00:00",
            "gross_amount": 100.00,
            "processor_fee": 3.00,
            "net_amount": 97.00,
            "reservation_id": "r1",
            "channel_reservation_id": "",
            "guest": "Guest",
            "listing": "Room",
            "payout_id": "po_old",
            "payout_assignment_status": "Assigned",
            "payout_assignment_method": "Date",
            "payout_date": "2026-07-05",
        },
        {
            "payment_event_id": "Main::refund",
            "processor": "Stripe",
            "processor_account": "Main",
            "transaction_id": "refund",
            "transaction_type": "refund",
            "source_id": "ch_1",
            "transaction_date": "2026-07-07 23:20:00",
            "available_date": "2026-07-07 23:20:00",
            "gross_amount": -54.54,
            "processor_fee": 0.00,
            "net_amount": -54.54,
            "reservation_id": "",
            "channel_reservation_id": "",
            "guest": "",
            "listing": "",
            "payout_id": "po_wrong",
            "payout_assignment_status": "Assigned",
            "payout_assignment_method": "Date",
            "payout_date": "2026-07-07",
        },
        {
            "payment_event_id": "Main::adjustment",
            "processor": "Stripe",
            "processor_account": "Main",
            "transaction_id": "adjustment",
            "transaction_type": "adjustment",
            "source_id": "ch_1",
            "transaction_date": "2026-07-07 23:20:00",
            "available_date": "2026-07-07 23:20:00",
            "gross_amount": 0.22,
            "processor_fee": 0.00,
            "net_amount": 0.22,
            "reservation_id": "",
            "channel_reservation_id": "",
            "guest": "",
            "listing": "",
            "payout_id": "po_wrong",
            "payout_assignment_status": "Assigned",
            "payout_assignment_method": "Date",
            "payout_date": "2026-07-07",
        },
        {
            "payment_event_id": "Main::charge_a",
            "processor": "Stripe",
            "processor_account": "Main",
            "transaction_id": "charge_a",
            "transaction_type": "charge",
            "source_id": "ch_a",
            "transaction_date": "2026-07-08 00:00:00",
            "available_date": "2026-07-09 00:00:00",
            "gross_amount": 100.70,
            "processor_fee": 3.62,
            "net_amount": 97.08,
            "reservation_id": "ra",
            "channel_reservation_id": "",
            "guest": "A",
            "listing": "Room 5",
            "payout_id": "po_target",
            "payout_assignment_status": "Assigned",
            "payout_assignment_method": "Date",
            "payout_date": "2026-07-10",
        },
        {
            "payment_event_id": "Main::charge_b",
            "processor": "Stripe",
            "processor_account": "Main",
            "transaction_id": "charge_b",
            "transaction_type": "charge",
            "source_id": "ch_b",
            "transaction_date": "2026-07-08 00:00:00",
            "available_date": "2026-07-09 00:00:00",
            "gross_amount": 95.00,
            "processor_fee": 3.44,
            "net_amount": 91.56,
            "reservation_id": "rb",
            "channel_reservation_id": "",
            "guest": "B",
            "listing": "Room 4",
            "payout_id": "po_target",
            "payout_assignment_status": "Assigned",
            "payout_assignment_method": "Date",
            "payout_date": "2026-07-10",
        },
    ]
    return pd.DataFrame(rows)


def payouts():
    return pd.DataFrame([
        {
            "payout_id": "po_old",
            "processor_account": "Main",
            "transaction_date": "2026-07-05",
            "payout_amount": 97.00,
        },
        {
            "payout_id": "po_wrong",
            "processor_account": "Main",
            "transaction_date": "2026-07-07",
            "payout_amount": 0.00,
        },
        {
            "payout_id": "po_target",
            "processor_account": "Main",
            "transaction_date": "2026-07-10",
            "payout_amount": 134.32,
        },
    ])


def test_source_metadata_is_inherited_without_reassignment():
    result = inherit_stripe_source_metadata(ledger())

    refund = result.loc[
        result["transaction_id"].eq("refund")
    ].iloc[0]

    assert refund["reservation_id"] == "r1"
    assert refund["guest"] == "Guest"
    assert refund["payout_id"] == "po_wrong"


def test_refund_and_adjustment_form_one_bundle():
    bundles = build_refund_bundles(ledger())

    assert len(bundles) == 1
    assert bundles.loc[0, "bundle_event_count"] == 2
    assert bundles.loc[0, "bundle_net"] == -54.32
    assert bundles.loc[0, "bundle_types"] == (
        "adjustment | refund"
    )


def test_exact_residual_move_reassigns_bundle():
    result, diagnostics = (
        reassign_refund_bundles_by_residual(
            ledger(),
            payouts(),
            tolerance=0.02,
            max_days=30,
        )
    )

    bundle_rows = result.loc[
        result["transaction_type"].isin(
            ["refund", "adjustment"]
        )
    ]

    assert set(bundle_rows["payout_id"]) == {
        "po_target"
    }
    assert set(
        bundle_rows["payout_assignment_method"]
    ) == {
        "Exact refund-bundle residual resolution"
    }
    assert diagnostics.loc[0, "status"] == "Reassigned"
    assert diagnostics.loc[
        0, "source_residual_after"
    ] == 0.0
    assert diagnostics.loc[
        0, "destination_residual_after"
    ] == 0.0


def test_no_exact_destination_does_not_move():
    changed_payouts = payouts()
    changed_payouts.loc[
        changed_payouts["payout_id"].eq("po_target"),
        "payout_amount",
    ] = 130.00

    result, diagnostics = (
        reassign_refund_bundles_by_residual(
            ledger(),
            changed_payouts,
            tolerance=0.02,
            max_days=30,
        )
    )

    refund = result.loc[
        result["transaction_id"].eq("refund")
    ].iloc[0]

    assert refund["payout_id"] == "po_wrong"
    assert diagnostics.loc[0, "status"] == (
        "Review Required"
    )
