from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def _relative_path(raw_path: str) -> str:
    path = Path(raw_path)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return raw_path


def _format_diagnostic(diagnostic: dict[str, Any]) -> str:
    location = diagnostic.get("range", {}).get("start", {})
    line = int(location.get("line", 0)) + 1
    column = int(location.get("character", 0)) + 1
    rule = diagnostic.get("rule")
    message = str(diagnostic.get("message", "")).replace("\xa0", " ")
    suffix = f" [{rule}]" if rule else ""
    return (
        f"{_relative_path(str(diagnostic.get('file', '<unknown>')))}:{line}:{column}: "
        f"{diagnostic.get('severity', 'unknown')}: {message}{suffix}"
    )


def main() -> int:
    executable = shutil.which("basedpyright")
    if executable is None:
        print("basedpyright executable not found in the current environment", file=sys.stderr)
        return 2

    result = subprocess.run(
        [executable, "--outputjson"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if not result.stdout.strip():
        print("basedpyright produced no JSON output", file=sys.stderr)
        return result.returncode or 2

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(result.stdout, end="")
        return result.returncode or 2

    diagnostics = payload.get("generalDiagnostics", [])
    for diagnostic in diagnostics:
        print(_format_diagnostic(diagnostic))

    summary = payload.get("summary", {})
    error_count = int(summary.get("errorCount", 0))
    warning_count = int(summary.get("warningCount", 0))
    information_count = int(summary.get("informationCount", 0))
    print(
        "basedpyright summary: "
        f"{error_count} errors, {warning_count} warnings, {information_count} notes"
    )
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
