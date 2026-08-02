# DSRL Phase 11C — Canceled Reservation Reconstruction

## Replaces

- `src/review/stripe_seed_candidates.py`
- `build_stripe_seed_candidates_v11.py`
- `tests/test_stripe_seed_candidates_v11.py`

## Adds

- `tests/test_canceled_reservation_reconstruction_v11.py`
- `docs/CANCELED_RESERVATION_RECONSTRUCTION_V11_PHASE_11C.md`

## Run

```powershell
python -m pytest
python build_stripe_seed_candidates_v11.py
```

Expected real-data behavior:

- Paul Weissmann: approval-eligible Booking.com reconstruction.
- Randal Jewell: approval-eligible VRBO 5.4% tax reconstruction.
- Johnathon Zawadzki: remains Not Eligible.
- unnamed large charge: remains Missing Reservation.

No candidates are promoted and no posting history is modified.
