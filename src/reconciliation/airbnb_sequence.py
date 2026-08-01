from __future__ import annotations

from collections import defaultdict

import pandas as pd


def _text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def _date_key(value: object) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return "UNKNOWN-DATE"
    return parsed.strftime("%Y%m%d")


def assign_airbnb_payouts_by_sequence(
    processor_transactions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Preserve the source row order and assign each Airbnb detail row to the
    most recent preceding Airbnb payout row.

    Blank Airbnb payout IDs receive deterministic IDs:
    AIRBNB-PAYOUT-YYYYMMDD-NN
    """
    required = {
        "processor",
        "transaction_id",
        "transaction_type",
        "source_id",
        "transaction_date",
        "gross_amount",
        "net_amount",
    }
    missing = sorted(required.difference(processor_transactions.columns))
    if missing:
        raise ValueError(
            f"Processor transactions missing columns: {missing}"
        )

    output = processor_transactions.copy()
    counters: dict[str, int] = defaultdict(int)
    current_payout_id = ""
    current_payout_date = pd.NaT
    diagnostic_rows: list[dict[str, object]] = []

    airbnb_indices = output.index[
        output["processor"].astype(str).str.strip().eq("Airbnb")
    ]

    for idx in airbnb_indices:
        transaction_type = _text(
            output.at[idx, "transaction_type"]
        ).lower()

        if transaction_type == "payout":
            existing_id = (
                _text(output.at[idx, "source_id"])
                or _text(output.at[idx, "transaction_id"])
            )

            if existing_id:
                payout_id = existing_id
                generated = "No"
            else:
                date_key = _date_key(
                    output.at[idx, "transaction_date"]
                )
                counters[date_key] += 1
                payout_id = (
                    f"AIRBNB-PAYOUT-{date_key}-"
                    f"{counters[date_key]:02d}"
                )
                generated = "Yes"

                output.at[idx, "transaction_id"] = payout_id
                output.at[idx, "source_id"] = payout_id

            current_payout_id = payout_id
            current_payout_date = pd.to_datetime(
                output.at[idx, "transaction_date"],
                errors="coerce",
            )

            diagnostic_rows.append(
                {
                    "row_index": idx,
                    "transaction_type": "payout",
                    "transaction_id": payout_id,
                    "assigned_payout_id": payout_id,
                    "assignment_method": (
                        "Existing payout ID"
                        if generated == "No"
                        else "Generated deterministic payout ID"
                    ),
                    "transaction_date": output.at[
                        idx, "transaction_date"
                    ],
                    "net_amount": float(
                        output.at[idx, "net_amount"]
                    ),
                }
            )
            continue

        if not current_payout_id:
            diagnostic_rows.append(
                {
                    "row_index": idx,
                    "transaction_type": transaction_type,
                    "transaction_id": _text(
                        output.at[idx, "transaction_id"]
                    ),
                    "assigned_payout_id": "",
                    "assignment_method": (
                        "Unassigned: no preceding payout row"
                    ),
                    "transaction_date": output.at[
                        idx, "transaction_date"
                    ],
                    "net_amount": float(
                        output.at[idx, "net_amount"]
                    ),
                }
            )
            continue

        output.at[idx, "source_id"] = current_payout_id

        diagnostic_rows.append(
            {
                "row_index": idx,
                "transaction_type": transaction_type,
                "transaction_id": _text(
                    output.at[idx, "transaction_id"]
                ),
                "assigned_payout_id": current_payout_id,
                "assignment_method": (
                    "Inherited preceding Airbnb payout"
                ),
                "transaction_date": output.at[
                    idx, "transaction_date"
                ],
                "net_amount": float(
                    output.at[idx, "net_amount"]
                ),
            }
        )

    diagnostics = pd.DataFrame(diagnostic_rows)

    return output, diagnostics


def summarize_airbnb_sequence_groups(
    sequenced_transactions: pd.DataFrame,
) -> pd.DataFrame:
    airbnb = sequenced_transactions.loc[
        sequenced_transactions["processor"]
        .astype(str)
        .str.strip()
        .eq("Airbnb")
    ].copy()

    payouts = airbnb.loc[
        airbnb["transaction_type"]
        .astype(str)
        .str.lower()
        .str.strip()
        .eq("payout")
    ].copy()

    details = airbnb.loc[
        ~airbnb["transaction_type"]
        .astype(str)
        .str.lower()
        .str.strip()
        .eq("payout")
    ].copy()

    detail_summary = (
        details.groupby("source_id", dropna=False)
        .agg(
            assigned_event_count=("transaction_id", "count"),
            assigned_event_net=("net_amount", "sum"),
        )
        .reset_index()
        .rename(columns={"source_id": "payout_id"})
    )

    payout_summary = payouts.assign(
        payout_id=payouts["source_id"].where(
            payouts["source_id"].astype(str).str.strip().ne(""),
            payouts["transaction_id"],
        )
    )[
        [
            "payout_id",
            "transaction_date",
            "net_amount",
        ]
    ].rename(columns={"net_amount": "payout_amount"})

    result = payout_summary.merge(
        detail_summary,
        on="payout_id",
        how="left",
    )

    result["assigned_event_count"] = (
        result["assigned_event_count"]
        .fillna(0)
        .astype(int)
    )
    result["assigned_event_net"] = (
        result["assigned_event_net"]
        .fillna(0.0)
        .round(2)
    )
    result["payout_amount"] = (
        result["payout_amount"].astype(float).round(2)
    )
    result["difference"] = (
        result["assigned_event_net"]
        - result["payout_amount"]
    ).round(2)
    result["balanced"] = result["difference"].abs().le(0.02)

    return result.sort_values(
        ["transaction_date", "payout_id"],
        ascending=[False, True],
    ).reset_index(drop=True)
