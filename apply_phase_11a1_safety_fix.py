from pathlib import Path

path = Path("src/review/exception_reconciliation.py")
text = path.read_text(encoding="utf-8")

start_marker = '            if not exact_family.empty:\n'
end_marker = '            elif not unresolved.empty:\n'

start = text.find(start_marker)
end = text.find(end_marker, start)

if start == -1 or end == -1:
    raise SystemExit(
        "ERROR: Expected Phase 11A.1 Stripe summary block was not found."
    )

replacement = """            if not blocked_rows.empty:
                confidence = "High"
                blocked = "Yes"
                sign_status = "Unsafe"
                recommended = (
                    "Do not create missing-original seeds; investigate excess or wrong payout assignment"
                )
                if not exact_family.empty:
                    exact_match_found = "Yes"
            elif not exact_family.empty:
                exact_match_found = "Yes"
                confidence = "High"
                recommended = _text(
                    exact_family.iloc[0].get(
                        "candidate_resolution"
                    )
                )
                proposed_effect = _money(
                    exact_family.iloc[0].get(
                        "family_gap"
                    )
                )
                sign_status, blocked = (
                    _sign_consistency(
                        difference,
                        proposed_effect,
                    )
                )
"""

new_text = text[:start] + replacement + text[end:]
path.write_text(new_text, encoding="utf-8")
print(f"Patched {path}")
