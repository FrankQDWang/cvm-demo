from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LINK_RE = re.compile(r"\[.+?\]\((/Users/frankqdwang/Agents/cvm-demo/[^)]+)\)")


def main() -> int:
    errors: list[str] = []
    for path in ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            target = Path(match.group(1))
            if not target.exists():
                errors.append(f"{path}: missing {target}")
    if errors:
        raise SystemExit("\n".join(errors))
    print("links=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
