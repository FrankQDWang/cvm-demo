from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOMAIN_ROOT = ROOT / "services/platform-api/src/cvm_platform/domain"
FORBIDDEN = ("fastapi", "sqlalchemy", "temporalio", "httpx")


def main() -> int:
    violations: list[str] = []
    for path in DOMAIN_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            if f"import {token}" in text or f"from {token}" in text:
                violations.append(f"{path}: forbidden import {token}")
    if violations:
        raise SystemExit("\n".join(violations))
    print("architecture=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
