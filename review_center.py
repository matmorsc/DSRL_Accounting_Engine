from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.review.overrides import (
    PAYMENT_MATCH_COLUMNS,
    PAYOUT_ADJUSTMENT_COLUMNS,
    append_unique_row,
)


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
PAYMENT_MATCHES = (
    ROOT / "config" / "manual_payment_matches.csv"
)
PAYOUT_ADJUSTMENTS = (
    ROOT / "config" / "payout_adjustments.csv"
)


def read_csv(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run the prerequisite reports first."
        )
    return pd.read_csv(path)


def prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def yes_no(text: str, default: bool = False) -> bool:
    marker = "Y/n" if default else "y/N"
    value = input(f"{text} ({marker}): ").strip().lower()

    if not value:
        return default
    return value in {"y", "yes"}


def review_payment_matches() -> int:
    review = read_csv("unlinked_stripe_review.csv")

    if review.empty:
        print("No unlinked Stripe events.")
        return 0

    accepted = 0

    for position, (_, row) in enumerate(
        review.iterrows(),
        start=1,
    ):
        print()
        print("=" * 72)
        print(
            f"PAYMENT MATCH {position} OF {len(review)}"
        )
        print("=" * 72)
        print(
            f"Event:   {row.get('payment_event_id', '')}"
        )
        print(
            f"Payout:  {row.get('payout_id', '')}"
        )
        print(
            f"Date:    {row.get('transaction_date', '')}"
        )
        print(
            f"Gross:   {row.get('gross_amount', '')}"
        )
        print(
            f"Guest:   {row.get('guest_metadata', '')}"
        )
        print(
            f"Listing: {row.get('listing_metadata', '')}"
        )
        print()

        for rank in range(1, 6):
            reservation_id = str(
                row.get(
                    f"candidate_{rank}_reservation_id",
                    "",
                )
            ).strip()
            channel_id = str(
                row.get(
                    f"candidate_{rank}_channel_id",
                    "",
                )
            ).strip()

            if not reservation_id and not channel_id:
                continue

            print(
                f"{rank}. score={row.get(f'candidate_{rank}_score', '')} "
                f"reservation={reservation_id} "
                f"channel={channel_id}"
            )
            print(
                f"   {row.get(f'candidate_{rank}_reason', '')}"
            )

        print()
        choice = prompt(
            "Choose 1-5, M for manual ID, S to skip, Q to quit",
            "S",
        ).upper()

        if choice == "Q":
            break
        if choice == "S":
            continue

        if choice == "M":
            reservation_id = prompt(
                "Guesty reservation ID"
            )
            channel_id = prompt(
                "Channel reservation ID (optional)"
            )
        elif choice in {"1", "2", "3", "4", "5"}:
            rank = int(choice)
            reservation_id = str(
                row.get(
                    f"candidate_{rank}_reservation_id",
                    "",
                )
            ).strip()
            channel_id = str(
                row.get(
                    f"candidate_{rank}_channel_id",
                    "",
                )
            ).strip()
        else:
            print("Invalid choice; skipped.")
            continue

        if not reservation_id and not channel_id:
            print("No reservation ID selected; skipped.")
            continue

        if not yes_no(
            f"Accept link to reservation {reservation_id or channel_id}?"
        ):
            continue

        notes = prompt(
            "Notes",
            "Confirmed during CSV Review Center",
        )

        append_unique_row(
            PAYMENT_MATCHES,
            {
                "payment_event_id": row.get(
                    "payment_event_id",
                    "",
                ),
                "reservation_id": reservation_id,
                "channel_reservation_id": channel_id,
                "status": "Accepted",
                "notes": notes,
            },
            PAYMENT_MATCH_COLUMNS,
            unique_columns=["payment_event_id"],
        )
        accepted += 1
        print("Saved.")

    return accepted


def review_payout_differences() -> int:
    review = read_csv("deposit_exception_review.csv")
    review = review.loc[
        review["primary_issue"]
        .astype(str)
        .str.strip()
        .eq("Unexplained payout difference")
    ].copy()

    if review.empty:
        print("No unexplained payout differences.")
        return 0

    saved = 0

    for position, (_, row) in enumerate(
        review.iterrows(),
        start=1,
    ):
        payout_id = str(row.get("payout_id", "")).strip()
        difference = float(row.get("difference", 0.0))
        balancing_amount = round(-difference, 2)

        print()
        print("=" * 72)
        print(
            f"PAYOUT DIFFERENCE {position} OF {len(review)}"
        )
        print("=" * 72)
        print(f"Payout:      {payout_id}")
        print(f"Processor:   {row.get('processor', '')}")
        print(f"Deposit:     {row.get('bank_amount', '')}")
        print(f"Draft total: {row.get('draft_total', '')}")
        print(f"Difference:  {difference:.2f}")
        print(
            f"Balancing adjustment would be: "
            f"{balancing_amount:.2f}"
        )
        print()
        print(
            "Only record an adjustment after confirming the cause "
            "in the processor payout detail."
        )

        if not yes_no(
            "Have you confirmed the cause and want to record an adjustment?"
        ):
            continue

        adjustment_type = prompt(
            "Adjustment type",
            "Processor Adjustment",
        )
        amount = float(
            prompt(
                "Adjustment amount",
                f"{balancing_amount:.2f}",
            )
        )
        account = prompt(
            "Exact QuickBooks account"
        )
        qb_class = prompt(
            "Exact QuickBooks class",
            "Hospitality",
        )
        description = prompt(
            "Description",
            adjustment_type,
        )
        notes = prompt(
            "Evidence / notes"
        )

        if not account:
            print("Account is required; skipped.")
            continue

        if not yes_no(
            f"Save {amount:.2f} to {account} / {qb_class}?"
        ):
            continue

        append_unique_row(
            PAYOUT_ADJUSTMENTS,
            {
                "payout_id": payout_id,
                "adjustment_type": adjustment_type,
                "amount": f"{amount:.2f}",
                "account": account,
                "class": qb_class,
                "description": description,
                "status": "Active",
                "notes": notes,
            },
            PAYOUT_ADJUSTMENT_COLUMNS,
            unique_columns=[
                "payout_id",
                "adjustment_type",
            ],
        )
        saved += 1
        print("Saved.")

    return saved


def main() -> int:
    print("DSRL CSV Review Center")
    print("=" * 40)
    print("1. Review unlinked Stripe payment matches")
    print("2. Review unexplained payout differences")
    print("3. Run both")
    print("Q. Quit")
    print()

    choice = prompt("Choose an option", "3").upper()

    try:
        accepted = 0
        adjustments = 0

        if choice in {"1", "3"}:
            accepted = review_payment_matches()

        if choice in {"2", "3"}:
            adjustments = review_payout_differences()

        if choice == "Q":
            return 0

    except KeyboardInterrupt:
        print("\nReview stopped. Saved decisions were preserved.")
        return 1
    except Exception as exc:
        print(f"ERROR: Review Center failed: {exc}")
        return 1

    print()
    print("=" * 40)
    print(f"Payment matches saved: {accepted}")
    print(f"Payout adjustments saved: {adjustments}")
    print()
    print("Next run:")
    print("  python build_deposit_drafts_v2.py")
    print("  python build_deposit_exception_review.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
