from __future__ import annotations

from typing import Any

import pandas as pd


REQUIRED_COLUMNS = {
    "processor",
    "processor_account",
    "transaction_id",
    "transaction_type",
    "source_id",
    "transaction_date",
    "available_date",
    "gross_amount",
    "processor_fee",
    "net_amount",
    "reservation_id",
    "channel_reservation_id",
    "guest",
    "listing",
    "source_file",
}


def _require(
    frame: pd.DataFrame,
    required: set[str],
    label: str,
) -> None:
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


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


def _metadata_score(row: pd.Series) -> int:
    fields = [
        "reservation_id",
        "channel_reservation_id",
        "guest",
        "listing",
    ]
    return sum(bool(_text(row.get(field))) for field in fields)


def build_stripe_charge_families(
    processor_transactions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Group Stripe balance transactions by Source.

    For charge-backed families, metadata is inherited from the best available
    family member, normally the original charge row. Every underlying balance
    transaction remains separate so refunds, adjustments, and fee refunds are
    not collapsed or hidden.
    """
    _require(
        processor_transactions,
        REQUIRED_COLUMNS,
        "Processor transactions",
    )

    stripe = processor_transactions.loc[
        processor_transactions["processor"]
        .astype(str)
        .str.strip()
        .eq("Stripe")
    ].copy()

    non_stripe = processor_transactions.loc[
        ~processor_transactions.index.isin(stripe.index)
    ].copy()

    stripe["charge_family_id"] = stripe.apply(
        lambda row: (
            _text(row.get("source_id"))
            or _text(row.get("transaction_id"))
        ),
        axis=1,
    )

    output_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []

    for family_id, family in stripe.groupby(
        "charge_family_id",
        dropna=False,
        sort=False,
    ):
        family = family.copy()

        candidates = family.loc[
            family["transaction_type"]
            .astype(str)
            .str.lower()
            .str.strip()
            .eq("charge")
        ].copy()

        if candidates.empty:
            candidates = family.copy()

        candidates["_metadata_score"] = candidates.apply(
            _metadata_score,
            axis=1,
        )
        candidates = candidates.sort_values(
            ["_metadata_score", "transaction_date"],
            ascending=[False, True],
        )
        metadata_source = candidates.iloc[0]

        reservation_id = _text(
            metadata_source.get("reservation_id")
        )
        channel_id = _text(
            metadata_source.get("channel_reservation_id")
        )
        guest = _text(metadata_source.get("guest"))
        listing = _text(metadata_source.get("listing"))

        if not any(
            [reservation_id, channel_id, guest, listing]
        ):
            diagnostic_rows.append(
                {
                    "charge_family_id": family_id,
                    "diagnostic_type": "No Family Metadata",
                    "detail": (
                        "No Stripe family member contained reservation or guest metadata."
                    ),
                    "family_event_count": len(family),
                    "family_net": round(
                        family["net_amount"]
                        .astype(float)
                        .sum(),
                        2,
                    ),
                }
            )

        event_types = (
            family["transaction_type"]
            .astype(str)
            .str.lower()
            .str.strip()
            .tolist()
        )

        if "refund" in event_types and "adjustment" not in event_types:
            diagnostic_rows.append(
                {
                    "charge_family_id": family_id,
                    "diagnostic_type": "Refund Without Adjustment",
                    "detail": (
                        "Refund family contains no fee-refund or adjustment component."
                    ),
                    "family_event_count": len(family),
                    "family_net": round(
                        family["net_amount"]
                        .astype(float)
                        .sum(),
                        2,
                    ),
                }
            )

        for _, event in family.iterrows():
            row = event.to_dict()
            row["charge_family_id"] = family_id
            row["family_reservation_id"] = reservation_id
            row["family_channel_reservation_id"] = channel_id
            row["family_guest"] = guest
            row["family_listing"] = listing
            row["family_metadata_inherited"] = (
                "Yes"
                if not _text(event.get("reservation_id"))
                and bool(reservation_id or channel_id)
                else "No"
            )
            output_rows.append(row)

    stripe_output = pd.DataFrame(output_rows)

    for column in [
        "charge_family_id",
        "family_reservation_id",
        "family_channel_reservation_id",
        "family_guest",
        "family_listing",
        "family_metadata_inherited",
    ]:
        non_stripe[column] = ""

    combined = pd.concat(
        [stripe_output, non_stripe],
        ignore_index=True,
        sort=False,
    )

    return combined, pd.DataFrame(diagnostic_rows)


def summarize_stripe_charge_families(
    family_transactions: pd.DataFrame,
) -> pd.DataFrame:
    stripe = family_transactions.loc[
        family_transactions["processor"]
        .astype(str)
        .str.strip()
        .eq("Stripe")
    ].copy()

    summary = (
        stripe.groupby(
            [
                "processor_account",
                "charge_family_id",
                "family_reservation_id",
                "family_channel_reservation_id",
                "family_guest",
                "family_listing",
            ],
            dropna=False,
        )
        .agg(
            family_event_count=("transaction_id", "count"),
            family_gross=("gross_amount", "sum"),
            family_fee=("processor_fee", "sum"),
            family_net=("net_amount", "sum"),
            first_event_date=("transaction_date", "min"),
            last_event_date=("transaction_date", "max"),
            event_types=(
                "transaction_type",
                lambda values: " | ".join(
                    sorted(
                        {
                            str(value).strip()
                            for value in values
                            if str(value).strip()
                        }
                    )
                ),
            ),
        )
        .reset_index()
    )

    for column in [
        "family_gross",
        "family_fee",
        "family_net",
    ]:
        summary[column] = (
            pd.to_numeric(
                summary[column],
                errors="coerce",
            )
            .fillna(0.0)
            .round(2)
        )

    return summary.sort_values(
        [
            "processor_account",
            "first_event_date",
            "charge_family_id",
        ]
    ).reset_index(drop=True)


def apply_family_metadata_to_payment_ledger(
    payment_ledger: pd.DataFrame,
) -> pd.DataFrame:
    output = payment_ledger.copy()

    for target, family_source in [
        ("reservation_id", "family_reservation_id"),
        (
            "channel_reservation_id",
            "family_channel_reservation_id",
        ),
        ("guest", "family_guest"),
        ("listing", "family_listing"),
    ]:
        if family_source not in output.columns:
            continue

        blank = (
            output[target]
            .astype(str)
            .str.strip()
            .isin({"", "nan", "None"})
        )
        output.loc[blank, target] = output.loc[
            blank,
            family_source,
        ]

    return output
