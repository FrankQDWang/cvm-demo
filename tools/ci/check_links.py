from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urldefrag


ROOT = Path(__file__).resolve().parents[2]
LINK_RE = re.compile(r"!?\[[^\]]+\]\(([^)]+)\)")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
IGNORED_ROOTS = {".repo-harness", ".venv", "node_modules"}


def _resolve_target(source: Path, raw_target: str) -> Path | None:
    target_text = urldefrag(raw_target.strip()).url.strip()
    if not target_text or target_text.startswith("#") or SCHEME_RE.match(target_text):
        return None
    if target_text.startswith("<") and target_text.endswith(">"):
        target_text = target_text[1:-1].strip()
    target_path = Path(target_text)
    if target_path.is_absolute():
        raise ValueError(f"{source}: absolute filesystem path links are forbidden: {target_text}")
    resolved = (source.parent / target_path).resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError(f"{source}: link escapes repo root: {target_text}")
    return resolved


def main() -> int:
    errors: list[str] = []
    for path in ROOT.rglob("*.md"):
        if any(part in IGNORED_ROOTS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            raw_target = match.group(1)
            try:
                target = _resolve_target(path, raw_target)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if target is not None and not target.exists():
                errors.append(f"{path}: missing {target}")
    if errors:
        raise SystemExit("\n".join(errors))
    print("links=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
