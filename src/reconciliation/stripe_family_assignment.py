from __future__ import annotations

import pandas as pd


def _text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def assign_stripe_families_to_payouts(
    payments: pd.DataFrame,
    payouts: pd.DataFrame,
) -> pd.DataFrame:
    """
    Assign all Stripe members of a charge family to one payout.

    The family's comparison date is the latest available date among its
    components. This prevents a refund and its related fee adjustment from being
    split across different payouts merely because individual rows share an
    earlier available date.

    This remains a fallback when no explicit payout reference exists.
    """
    output = payments.copy()

    stripe_mask = (
        output["processor"]
        .astype(str)
        .str.strip()
        .eq("Stripe")
    )

    stripe = output.loc[stripe_mask].copy()

    if "charge_family_id" not in stripe.columns:
        return output

    for (
        account,
        family_id,
    ), family in stripe.groupby(
        ["processor_account", "charge_family_id"],
        dropna=False,
        sort=False,
    ):
        if not _text(family_id):
            continue

        account_payouts = payouts.loc[
            payouts["processor_account"]
            .astype(str)
            .str.strip()
            .eq(str(account).strip())
        ].copy()

        if account_payouts.empty:
            output.loc[
                family.index,
                "payout_assignment_status",
            ] = "No Payout Source"
            continue

        exact_reference = account_payouts.loc[
            account_payouts["payout_id"]
            .astype(str)
            .str.strip()
            .eq(_text(family.iloc[0].get("source_id")))
        ]

        if not exact_reference.empty:
            selected = exact_reference.iloc[0]
            method = "Exact Stripe payout reference"
        else:
            available_dates = pd.to_datetime(
                family["available_date"],
                errors="coerce",
            )
            transaction_dates = pd.to_datetime(
                family["transaction_date"],
                errors="coerce",
            )
            comparison_date = available_dates.max()

            if pd.isna(comparison_date):
                comparison_date = transaction_dates.max()

            if pd.isna(comparison_date):
                output.loc[
                    family.index,
                    "payout_assignment_status",
                ] = "Missing Event Date"
                continue

            payout_dates = pd.to_datetime(
                account_payouts["transaction_date"],
                errors="coerce",
            )

            candidates = account_payouts.loc[
                payout_dates >= comparison_date.normalize()
            ].copy()

            if candidates.empty:
                output.loc[
                    family.index,
                    "payout_assignment_status",
                ] = "Pending Future Payout"
                continue

            candidates["_payout_date"] = pd.to_datetime(
                candidates["transaction_date"],
                errors="coerce",
            )
            candidates = candidates.sort_values(
                ["_payout_date", "payout_id"]
            )
            selected = candidates.iloc[0]
            method = (
                "Charge family assigned to first payout on or after latest family date"
            )

        output.loc[
            family.index,
            "payout_id",
        ] = selected["payout_id"]
        output.loc[
            family.index,
            "payout_assignment_status",
        ] = "Assigned"
        output.loc[
            family.index,
            "payout_assignment_method",
        ] = method
        output.loc[
            family.index,
            "payout_date",
        ] = selected["transaction_date"]

    return output
