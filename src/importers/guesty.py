from pathlib import Path
import pandas as pd

REQUIRED_COLUMNS = {
    "GUEST", "LISTING'S NICKNAME", "CONFIRMATION DATE", "CHECK-IN", "CHECK-OUT",
    "PAYMENT METHOD", "TOTAL PAID", "TOTAL REFUNDED",
    "CHANNEL RESERVATION ID", "RESERVATION ID",
}

def load_guesty_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"Guesty export is missing columns: {sorted(missing)}")
    return frame
