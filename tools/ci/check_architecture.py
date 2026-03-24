from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOMAIN_ROOT = ROOT / "services/platform-api/src/cvm_platform/domain"
APPLICATION_ROOT = ROOT / "services/platform-api/src/cvm_platform/application"
LAYER_RULES = {
    DOMAIN_ROOT: ("fastapi", "sqlalchemy", "temporalio", "httpx"),
    APPLICATION_ROOT: ("sqlalchemy", "cvm_platform.infrastructure", "cvm_platform.settings"),
}


def main() -> int:
    violations: list[str] = []
    for root, forbidden_tokens in LAYER_RULES.items():
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                if f"import {token}" in text or f"from {token}" in text:
                    violations.append(f"{path}: forbidden import {token}")
    if violations:
        raise SystemExit("\n".join(violations))
    print("architecture=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
