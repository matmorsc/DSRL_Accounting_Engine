from __future__ import annotations

import pandas as pd

PAYMENT_TYPES = {"charge", "payment", "reservation", "refund", "adjustment"}
PAYOUT_TYPES = {"payout"}


def _require(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def build_payment_ledger(
    processor_transactions: pd.DataFrame,
) -> pd.DataFrame:
    required = {
        "processor", "processor_account", "transaction_id",
        "transaction_type", "source_id", "transaction_date",
        "available_date", "gross_amount", "processor_fee",
        "net_amount", "reservation_id",
        "channel_reservation_id", "guest", "listing", "source_file",
    }
    _require(processor_transactions, required, "Processor transactions")

    payments = processor_transactions.loc[
        processor_transactions["transaction_type"].isin(PAYMENT_TYPES)
    ].copy()

    payments["payment_event_id"] = (
        payments["processor_account"].astype(str)
        + "::"
        + payments["transaction_id"].astype(str)
    )
    payments["payout_id"] = ""
    payments["payout_assignment_status"] = "Unassigned"
    payments["payout_assignment_method"] = ""
    payments["payout_date"] = pd.NaT

    columns = [
        "payment_event_id", "processor", "processor_account",
        "transaction_id", "transaction_type", "source_id",
        "transaction_date", "available_date", "gross_amount",
        "processor_fee", "net_amount", "reservation_id",
        "channel_reservation_id", "guest", "listing",
        "payout_id", "payout_assignment_status",
        "payout_assignment_method", "payout_date", "source_file",
    ]
    return payments[columns].sort_values(
        ["processor_account", "available_date", "transaction_date"],
        na_position="last",
    ).reset_index(drop=True)


def build_payout_ledger(
    processor_transactions: pd.DataFrame,
) -> pd.DataFrame:
    required = {
        "processor", "processor_account", "transaction_id",
        "transaction_type", "source_id", "transaction_date",
        "net_amount", "source_file",
    }
    _require(processor_transactions, required, "Processor transactions")

    payouts = processor_transactions.loc[
        processor_transactions["transaction_type"].isin(PAYOUT_TYPES)
    ].copy()

    payouts["payout_id"] = payouts["source_id"].where(
        payouts["source_id"].astype(str).str.strip().ne(""),
        payouts["transaction_id"],
    )
    payouts["payout_amount"] = payouts["net_amount"].astype(float).abs()
    payouts["assigned_event_count"] = 0
    payouts["assigned_event_net"] = 0.0
    payouts["allocation_difference"] = 0.0
    payouts["allocation_status"] = "Unallocated"
    payouts["bank_transaction_id"] = ""
    payouts["bank_transaction_date"] = pd.NaT
    payouts["bank_amount"] = 0.0
    payouts["bank_difference"] = 0.0
    payouts["bank_match_status"] = "Unmatched"
    payouts["bank_match_method"] = ""

    columns = [
        "payout_id", "processor", "processor_account", "transaction_id",
        "transaction_date", "payout_amount", "assigned_event_count",
        "assigned_event_net", "allocation_difference",
        "allocation_status", "bank_transaction_id",
        "bank_transaction_date", "bank_amount", "bank_difference",
        "bank_match_status", "bank_match_method", "source_file",
    ]
    return payouts[columns].sort_values(
        ["processor_account", "transaction_date"],
        na_position="last",
    ).reset_index(drop=True)


def assign_payment_events_to_payouts(
    payments: pd.DataFrame,
    payouts: pd.DataFrame,
) -> pd.DataFrame:
    output = payments.copy()

    for account in sorted(output["processor_account"].dropna().unique()):
        account_payouts = payouts.loc[
            payouts["processor_account"].eq(account)
        ].sort_values("transaction_date")

        if account_payouts.empty:
            continue

        for idx in output.index[
            output["processor_account"].eq(account)
        ]:
            available = pd.to_datetime(
                output.at[idx, "available_date"], errors="coerce"
            )
            transaction_date = pd.to_datetime(
                output.at[idx, "transaction_date"], errors="coerce"
            )
            comparison = available if pd.notna(available) else transaction_date

            if pd.isna(comparison):
                output.at[idx, "payout_assignment_status"] = "Missing Event Date"
                continue

            candidates = account_payouts.loc[
                pd.to_datetime(
                    account_payouts["transaction_date"],
                    errors="coerce",
                ).dt.normalize()
                >= comparison.normalize()
            ]

            if candidates.empty:
                output.at[idx, "payout_assignment_status"] = "Pending Future Payout"
                continue

            selected = candidates.iloc[0]
            output.at[idx, "payout_id"] = selected["payout_id"]
            output.at[idx, "payout_assignment_status"] = "Assigned"
            output.at[
                idx, "payout_assignment_method"
            ] = "First payout on or after available date"
            output.at[idx, "payout_date"] = selected["transaction_date"]

    return output


def summarize_payout_allocations(
    payments: pd.DataFrame,
    payouts: pd.DataFrame,
) -> pd.DataFrame:
    assigned = payments.loc[
        payments["payout_assignment_status"].eq("Assigned")
        & payments["payout_id"].astype(str).str.strip().ne("")
    ]

    summary = (
        assigned.groupby("payout_id", dropna=False)
        .agg(
            assigned_event_count=("payment_event_id", "count"),
            assigned_event_net=("net_amount", "sum"),
        )
        .reset_index()
    )

    output = payouts.drop(
        columns=[
            "assigned_event_count", "assigned_event_net",
            "allocation_difference", "allocation_status",
        ],
        errors="ignore",
    ).merge(summary, on="payout_id", how="left")

    output["assigned_event_count"] = (
        output["assigned_event_count"].fillna(0).astype(int)
    )
    output["assigned_event_net"] = (
        output["assigned_event_net"].fillna(0.0).round(2)
    )
    output["allocation_difference"] = (
        output["assigned_event_net"] - output["payout_amount"]
    ).round(2)
    output["allocation_status"] = "Difference"
    output.loc[
        output["assigned_event_count"].eq(0), "allocation_status"
    ] = "Unallocated"
    output.loc[
        output["assigned_event_count"].gt(0)
        & output["allocation_difference"].abs().le(0.02),
        "allocation_status",
    ] = "Fully Allocated"
    return output


def match_payouts_to_bank(
    payouts: pd.DataFrame,
    bank_transactions: pd.DataFrame,
    date_tolerance_days: int = 5,
    amount_tolerance: float = 0.02,
) -> pd.DataFrame:
    output = payouts.copy()
    used_bank_ids: set[str] = set()

    for idx, payout in output.iterrows():
        payout_date = pd.to_datetime(
            payout["transaction_date"], errors="coerce"
        )
        if pd.isna(payout_date):
            continue

        candidates = bank_transactions.loc[
            bank_transactions["amount"].astype(float).gt(0)
        ].copy()

        processor = str(payout["processor"]).strip()
        if processor:
            processor_only = candidates.loc[
                candidates["identified_processor"]
                .astype(str).str.strip().eq(processor)
            ]
            if not processor_only.empty:
                candidates = processor_only

        candidates = candidates.loc[
            ~candidates["transaction_id"].astype(str).isin(used_bank_ids)
        ].copy()

        candidates["amount_difference"] = (
            candidates["amount"].astype(float)
            - float(payout["payout_amount"])
        ).abs()
        candidates["date_difference_days"] = (
            pd.to_datetime(
                candidates["transaction_date"], errors="coerce"
            ).dt.normalize()
            - payout_date.normalize()
        ).dt.days.abs()

        exact = candidates.loc[
            candidates["amount_difference"].le(amount_tolerance)
            & candidates["date_difference_days"].le(date_tolerance_days)
        ].sort_values(
            ["date_difference_days", "amount_difference", "transaction_date"]
        )

        if exact.empty:
            continue

        selected = exact.iloc[0]
        bank_id = str(selected["transaction_id"]).strip()
        used_bank_ids.add(bank_id)

        output.at[idx, "bank_transaction_id"] = bank_id
        output.at[idx, "bank_transaction_date"] = selected["transaction_date"]
        output.at[idx, "bank_amount"] = float(selected["amount"])
        output.at[idx, "bank_difference"] = round(
            float(selected["amount"]) - float(payout["payout_amount"]), 2
        )
        output.at[idx, "bank_match_status"] = "Matched"
        output.at[
            idx, "bank_match_method"
        ] = "Exact amount within date tolerance"

    return output


def build_payout_reconciliation(
    payments: pd.DataFrame,
    payouts: pd.DataFrame,
    bank_transactions: pd.DataFrame,
    date_tolerance_days: int = 5,
    amount_tolerance: float = 0.02,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    assigned = assign_payment_events_to_payouts(payments, payouts)
    allocated = summarize_payout_allocations(assigned, payouts)
    matched = match_payouts_to_bank(
        allocated,
        bank_transactions,
        date_tolerance_days=date_tolerance_days,
        amount_tolerance=amount_tolerance,
    )
    return assigned, matched
