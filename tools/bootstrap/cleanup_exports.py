from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path


EXPORT_DIR = Path("var/exports")
TTL_DAYS = int(os.getenv("CVM_EXPORT_TTL_DAYS", "7"))


def main() -> int:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=TTL_DAYS)
    removed = 0
    for path in EXPORT_DIR.glob("*"):
        if not path.is_file():
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if modified < cutoff:
            path.unlink()
            removed += 1
    print(f"removed={removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
