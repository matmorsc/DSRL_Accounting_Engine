from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


def write_source_inventory(
    sources: dict[str, list[Path]],
    output_dir: Path,
) -> Path:
    rows: list[dict[str, object]] = []

    for source_name, paths in sources.items():
        for path in paths:
            rows.append(
                {
                    "source": source_name,
                    "file": path.name,
                    "full_path": str(path),
                    "size_bytes": path.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        path.stat().st_mtime
                    ).isoformat(timespec="seconds"),
                }
            )

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output_path = output_dir / f"source_inventory_{timestamp}.csv"

    pd.DataFrame(rows).to_csv(output_path, index=False)
    return output_path
