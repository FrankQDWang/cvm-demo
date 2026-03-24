from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    required = [
        ROOT / "libs/py/contracts-generated/src/cvm_contracts_generated/platform_api.py",
        ROOT / "libs/ts/api-client-generated/src/generated/services/DefaultService.ts",
        ROOT / "libs/ts/api-client-generated/src/index.ts",
        ROOT / "docs/_generated/openapi-platform-api.md",
        ROOT / "docs/_generated/asyncapi-platform-events.md",
        ROOT / "docs/_generated/external-cts.md",
    ]
    missing = [str(path) for path in required if not path.exists() or not path.read_text(encoding="utf-8").strip()]
    if missing:
        raise SystemExit("missing generated artifacts:\n" + "\n".join(missing))
    print("generated=clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
