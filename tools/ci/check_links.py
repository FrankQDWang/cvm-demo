from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urldefrag


ROOT = Path(__file__).resolve().parents[2]
LINK_RE = re.compile(r"\[.+?\]\((/Users/frankqdwang/Agents/cvm-demo/[^)]+)\)")
IGNORED_ROOTS = {".repo-harness", ".venv", "node_modules"}


def main() -> int:
    errors: list[str] = []
    for path in ROOT.rglob("*.md"):
        if any(part in IGNORED_ROOTS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            raw_target = match.group(1)
            target = Path(urldefrag(raw_target).url)
            if not target.exists():
                errors.append(f"{path}: missing {target}")
    if errors:
        raise SystemExit("\n".join(errors))
    print("links=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
