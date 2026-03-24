from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
IGNORED_DIRS = {
    ".git",
    ".angular",
    ".venv",
    "node_modules",
    "dist",
    "__pycache__",
}
IGNORED_FILE_NAMES = {
    "check_forbidden_runtime_artifacts.py",
}


def build_forbidden_tokens() -> list[str]:
    return [
        "".join(("sql", "ite")),
        "".join(("py", "sql", "ite")),
        "".join(("test.", "sql", "ite3")),
        "".join(("eval-blocking.", "sql", "ite3")),
    ]


def iter_candidate_files(root: Path) -> list[Path]:
    results: list[Path] = []
    for path in root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.name in IGNORED_FILE_NAMES:
            continue
        if path.is_file():
            results.append(path)
    return results


def main() -> int:
    forbidden_tokens = build_forbidden_tokens()
    matches: list[str] = []

    for path in iter_candidate_files(REPO_ROOT):
        if any(token in path.as_posix() for token in forbidden_tokens):
            matches.append(path.relative_to(REPO_ROOT).as_posix())
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for token in forbidden_tokens:
            if token in content:
                matches.append(path.relative_to(REPO_ROOT).as_posix())
                break

    if matches:
        rendered = "\n".join(f"- {match}" for match in sorted(set(matches)))
        raise SystemExit(f"Forbidden local DB references found:\n{rendered}")

    print("Forbidden local DB references check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
