from __future__ import annotations

from pathlib import Path


def require_fresh_artifact(
    path: Path,
    *,
    generated_by: str,
    newer_than: tuple[Path, ...] = (),
) -> Path:
    """Require a derived file to exist and be at least as new as its inputs."""
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run `{generated_by}` first."
        )

    missing_inputs = [
        dependency
        for dependency in newer_than
        if not dependency.exists()
    ]
    if missing_inputs:
        missing = ", ".join(str(dependency) for dependency in missing_inputs)
        raise FileNotFoundError(f"Missing upstream artifact(s): {missing}.")

    stale_inputs = [
        dependency
        for dependency in newer_than
        if path.stat().st_mtime_ns < dependency.stat().st_mtime_ns
    ]
    if stale_inputs:
        newest = max(
            stale_inputs,
            key=lambda dependency: dependency.stat().st_mtime_ns,
        )
        raise RuntimeError(
            f"Stale derived artifact: {path} is older than {newest}. "
            f"Run `{generated_by}` first."
        )

    return path
