from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "REPOSITORY_SNAPSHOT.md"


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or result.stderr.strip()


def main() -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")

    content = f"""# Repository Snapshot

Generated: {timestamp}

## Branch and Status

```text
{git("status", "--short", "--branch")}
```

## Recent Commits

```text
{git("log", "--oneline", "-15")}
```

## Tracked Project Files

```text
{git("ls-files")}
```

## Test Command

```powershell
python -m pytest
```

## Pipeline Command

```powershell
python run.py
```
"""

    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Repository snapshot written to: {OUTPUT}")


if __name__ == "__main__":
    main()
