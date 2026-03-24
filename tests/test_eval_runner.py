from __future__ import annotations

from cvm_eval_runner.cli import run_blocking_suite


def test_blocking_suite_passes() -> None:
    result = run_blocking_suite()
    assert result["passed"] is True
