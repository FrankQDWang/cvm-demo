from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def require_keys(path: Path, keys: list[str]) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    missing = [key for key in keys if key not in data]
    if missing:
        raise SystemExit(f"{path} missing keys: {', '.join(missing)}")


def main() -> int:
    require_keys(ROOT / "contracts/openapi/platform-api.openapi.yaml", ["openapi", "paths", "components"])
    require_keys(ROOT / "contracts/asyncapi/platform-events.asyncapi.yaml", ["asyncapi", "channels", "components"])
    require_keys(ROOT / "contracts/external/cts.validated.yaml", ["openapi", "paths", "components"])
    print("contracts=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
