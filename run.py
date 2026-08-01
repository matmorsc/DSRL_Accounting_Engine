from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config" / "settings.yaml"

def main() -> int:
    print("DSRL Accounting Engine")
    print("=" * 24)
    if not CONFIG.exists():
        print(f"Missing configuration: {CONFIG}")
        return 1
    with CONFIG.open("r", encoding="utf-8") as handle:
        settings = yaml.safe_load(handle)
    print(f"Business: {settings['business']['name']}")
    print(f"Monthly threshold: {settings['classification']['monthly_night_threshold']} nights")
    print("Project structure is valid.")
    print("Next milestone: implement V4 from raw exports.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
