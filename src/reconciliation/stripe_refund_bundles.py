from __future__ import annotations

from typing import Any

import pandas as pd


REFUND_BUNDLE_TYPES = {
    "refund",
    "adjustment",
    "reversal",
    "dispute",
}


def _text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def _money(value: object) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def _timestamp_key(value: object) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def inherit_stripe_source_metadata(
    payment_ledger: pd.DataFrame,
) -> pd.DataFrame:
    """
    Use Stripe Source only to inherit reservation metadata.

    This does not change payout assignments.
    """
    output = payment_ledger.copy()

    stripe = output.loc[
        output["processor"]
        .astype(str)
        .str.strip()
        .eq("Stripe")
    ].copy()

    metadata_lookup: dict[tuple[str, str], pd.Series] = {}

    for (account, source_id), family in stripe.groupby(
        ["processor_account", "source_id"],
        dropna=False,
        sort=False,
    ):
        source_id = _text(source_id)
        if not source_id:
            continue

        candidates = family.copy()
        candidates["_metadata_score"] = candidates.apply(
            lambda row: sum(
                bool(_text(row.get(field)))
                for field in [
                    "reservation_id",
                    "channel_reservation_id",
                    "guest",
                    "listing",
                ]
            ),
            axis=1,
        )
        candidates["_is_charge"] = (
            candidates["transaction_type"]
            .astype(str)
            .str.lower()
            .str.strip()
            .eq("charge")
            .astype(int)
        )
        candidates = candidates.sort_values(
            ["_metadata_score", "_is_charge", "transaction_date"],
            ascending=[False, False, True],
        )
        metadata_lookup[
            (_text(account), source_id)
        ] = candidates.iloc[0]

    output["stripe_metadata_inherited"] = "No"

    for idx, event in output.loc[
        output["processor"]
        .astype(str)
        .str.strip()
        .eq("Stripe")
    ].iterrows():
        key = (
            _text(event.get("processor_account")),
            _text(event.get("source_id")),
        )
        metadata = metadata_lookup.get(key)
        if metadata is None:
            continue

        changed = False

        for field in [
            "reservation_id",
            "channel_reservation_id",
            "guest",
            "listing",
        ]:
            if not _text(output.at[idx, field]):
                inherited = _text(metadata.get(field))
                if inherited:
                    output.at[idx, field] = inherited
                    changed = True

        if changed:
            output.at[
                idx,
                "stripe_metadata_inherited",
            ] = "Yes"

    return output


def build_refund_bundles(
    payment_ledger: pd.DataFrame,
) -> pd.DataFrame:
    """
    Group refund-related Stripe balance rows by account + Source + timestamp.

    A valid bundle must contain a refund-like row. A lone generic adjustment
    is not automatically treated as a refund bundle.
    """
    stripe = payment_ledger.loc[
        payment_ledger["processor"]
        .astype(str)
        .str.strip()
        .eq("Stripe")
    ].copy()

    stripe["_type"] = (
        stripe["transaction_type"]
        .astype(str)
        .str.lower()
        .str.strip()
    )
    stripe = stripe.loc[
        stripe["_type"].isin(REFUND_BUNDLE_TYPES)
    ].copy()

    stripe["_timestamp_key"] = stripe["transaction_date"].apply(
        _timestamp_key
    )

    rows: list[dict[str, Any]] = []

    for (
        account,
        source_id,
        timestamp,
    ), group in stripe.groupby(
        [
            "processor_account",
            "source_id",
            "_timestamp_key",
        ],
        dropna=False,
        sort=False,
    ):
        event_types = set(group["_type"])
        if "refund" not in event_types:
            continue

        payout_ids = sorted(
            {
                _text(value)
                for value in group["payout_id"]
                if _text(value)
            }
        )

        rows.append(
            {
                "bundle_id": (
                    f"{_text(account)}::{_text(source_id)}::{timestamp}"
                ),
                "processor_account": _text(account),
                "source_id": _text(source_id),
                "transaction_timestamp": timestamp,
                "bundle_event_count": len(group),
                "bundle_event_ids": " | ".join(
                    sorted(
                        _text(value)
                        for value in group["payment_event_id"]
                    )
                ),
                "bundle_types": " | ".join(
                    sorted(event_types)
                ),
                "bundle_net": round(
                    pd.to_numeric(
                        group["net_amount"],
                        errors="coerce",
                    )
                    .fillna(0.0)
                    .sum(),
                    2,
                ),
                "current_payout_ids": " | ".join(payout_ids),
                "single_current_payout": (
                    payout_ids[0]
                    if len(payout_ids) == 1
                    else ""
                ),
            }
        )

    return pd.DataFrame(rows)


def _payout_residuals(
    payment_ledger: pd.DataFrame,
    payout_ledger: pd.DataFrame,
) -> dict[str, float]:
    assigned = payment_ledger.loc[
        payment_ledger["payout_assignment_status"]
        .astype(str)
        .str.strip()
        .eq("Assigned")
        & payment_ledger["payout_id"]
        .astype(str)
        .str.strip()
        .ne("")
    ].copy()

    event_net = (
        assigned.groupby("payout_id")["net_amount"]
        .sum()
        .to_dict()
    )

    residuals: dict[str, float] = {}

    for _, payout in payout_ledger.iterrows():
        payout_id = _text(payout.get("payout_id"))
        if not payout_id:
            continue

        assigned_net = float(event_net.get(payout_id, 0.0))
        payout_amount = _money(payout.get("payout_amount"))
        residuals[payout_id] = round(
            assigned_net - payout_amount,
            2,
        )

    return residuals


def reassign_refund_bundles_by_residual(
    payment_ledger: pd.DataFrame,
    payout_ledger: pd.DataFrame,
    *,
    tolerance: float = 0.02,
    max_days: int = 30,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Move a Stripe refund bundle only when the move resolves both the source and
    destination payout residuals within tolerance and strictly improves the
    combined residual.

    The algorithm does not guess among multiple exact candidates.
    """
    output = payment_ledger.copy()
    bundles = build_refund_bundles(output)
    residuals = _payout_residuals(output, payout_ledger)

    payout_index = {
        _text(row["payout_id"]): row
        for _, row in payout_ledger.iterrows()
        if _text(row["payout_id"])
    }

    diagnostic_rows: list[dict[str, Any]] = []

    for _, bundle in bundles.iterrows():
        bundle_id = _text(bundle.get("bundle_id"))
        current_payout = _text(
            bundle.get("single_current_payout")
        )
        bundle_net = _money(bundle.get("bundle_net"))
        account = _text(
            bundle.get("processor_account")
        )
        timestamp = pd.to_datetime(
            bundle.get("transaction_timestamp"),
            errors="coerce",
        )

        base_diag = {
            "bundle_id": bundle_id,
            "processor_account": account,
            "source_id": _text(bundle.get("source_id")),
            "transaction_timestamp": bundle.get(
                "transaction_timestamp"
            ),
            "bundle_event_count": int(
                bundle.get("bundle_event_count", 0)
            ),
            "bundle_types": _text(
                bundle.get("bundle_types")
            ),
            "bundle_net": bundle_net,
            "current_payout_id": current_payout,
            "current_payout_residual_before": residuals.get(
                current_payout,
                0.0,
            ),
        }

        if not current_payout:
            diagnostic_rows.append(
                {
                    **base_diag,
                    "status": "Review Required",
                    "selected_payout_id": "",
                    "selected_payout_residual_before": "",
                    "source_residual_after": "",
                    "destination_residual_after": "",
                    "improvement": "",
                    "detail": (
                        "Bundle events do not share one current payout."
                    ),
                }
            )
            continue

        current_row = payout_index.get(current_payout)
        if current_row is None:
            diagnostic_rows.append(
                {
                    **base_diag,
                    "status": "Review Required",
                    "selected_payout_id": "",
                    "selected_payout_residual_before": "",
                    "source_residual_after": "",
                    "destination_residual_after": "",
                    "improvement": "",
                    "detail": "Current payout missing from payout ledger.",
                }
            )
            continue

        current_residual = residuals.get(
            current_payout,
            0.0,
        )

        candidates: list[dict[str, Any]] = []

        for payout_id, payout in payout_index.items():
            if payout_id == current_payout:
                continue

            if _text(
                payout.get("processor_account")
            ) != account:
                continue

            payout_date = pd.to_datetime(
                payout.get("transaction_date"),
                errors="coerce",
            )

            if pd.notna(timestamp) and pd.notna(payout_date):
                day_distance = abs(
                    (payout_date.normalize() - timestamp.normalize()).days
                )
                if day_distance > max_days:
                    continue
            else:
                day_distance = 999999

            destination_residual = residuals.get(
                payout_id,
                0.0,
            )

            source_after = round(
                current_residual - bundle_net,
                2,
            )
            destination_after = round(
                destination_residual + bundle_net,
                2,
            )

            before = round(
                abs(current_residual)
                + abs(destination_residual),
                2,
            )
            after = round(
                abs(source_after)
                + abs(destination_after),
                2,
            )
            improvement = round(before - after, 2)

            if (
                abs(source_after) <= tolerance
                and abs(destination_after) <= tolerance
                and improvement > tolerance
            ):
                candidates.append(
                    {
                        "payout_id": payout_id,
                        "destination_residual": destination_residual,
                        "source_after": source_after,
                        "destination_after": destination_after,
                        "improvement": improvement,
                        "day_distance": day_distance,
                    }
                )

        candidates.sort(
            key=lambda item: (
                item["day_distance"],
                -item["improvement"],
                item["payout_id"],
            )
        )

        if len(candidates) != 1:
            detail = (
                "No exact residual-resolving destination found."
                if not candidates
                else (
                    f"{len(candidates)} exact destinations found; "
                    "automatic move withheld."
                )
            )
            diagnostic_rows.append(
                {
                    **base_diag,
                    "status": "Review Required",
                    "selected_payout_id": "",
                    "selected_payout_residual_before": "",
                    "source_residual_after": "",
                    "destination_residual_after": "",
                    "improvement": "",
                    "detail": detail,
                }
            )
            continue

        selected = candidates[0]
        selected_payout = selected["payout_id"]

        bundle_mask = (
            output["processor"]
            .astype(str)
            .str.strip()
            .eq("Stripe")
            & output["processor_account"]
            .astype(str)
            .str.strip()
            .eq(account)
            & output["source_id"]
            .astype(str)
            .str.strip()
            .eq(_text(bundle.get("source_id")))
            & output["transaction_date"]
            .apply(_timestamp_key)
            .eq(
                _text(
                    bundle.get("transaction_timestamp")
                )
            )
            & output["transaction_type"]
            .astype(str)
            .str.lower()
            .str.strip()
            .isin(REFUND_BUNDLE_TYPES)
        )

        selected_row = payout_index[selected_payout]

        output.loc[
            bundle_mask,
            "payout_id",
        ] = selected_payout
        output.loc[
            bundle_mask,
            "payout_assignment_status",
        ] = "Assigned"
        output.loc[
            bundle_mask,
            "payout_assignment_method",
        ] = "Exact refund-bundle residual resolution"
        output.loc[
            bundle_mask,
            "payout_date",
        ] = selected_row.get("transaction_date")

        residuals[current_payout] = selected[
            "source_after"
        ]
        residuals[selected_payout] = selected[
            "destination_after"
        ]

        diagnostic_rows.append(
            {
                **base_diag,
                "status": "Reassigned",
                "selected_payout_id": selected_payout,
                "selected_payout_residual_before": selected[
                    "destination_residual"
                ],
                "source_residual_after": selected[
                    "source_after"
                ],
                "destination_residual_after": selected[
                    "destination_after"
                ],
                "improvement": selected["improvement"],
                "detail": (
                    "Refund bundle moved because it exactly resolved "
                    "both payout residuals."
                ),
            }
        )

    return output, pd.DataFrame(diagnostic_rows)
