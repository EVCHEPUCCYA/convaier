from __future__ import annotations

import logging
import re

from convaier.context import PipelineContext, TestResults
from convaier.stages import Stage, StageResult, register
from convaier.util.proc import run_command

log = logging.getLogger("convaier")

# Matches pytest summary like: "5 passed, 1 failed, 2 skipped"
_PYTEST_SUMMARY_RE = re.compile(
    r"(\d+)\s+passed|(\d+)\s+failed|(\d+)\s+skipped"
)


def _parse_pytest_output(stdout: str) -> TestResults:
    results = TestResults(output=stdout)
    for match in _PYTEST_SUMMARY_RE.finditer(stdout):
        if match.group(1):
            results.passed = int(match.group(1))
        if match.group(2):
            results.failed = int(match.group(2))
        if match.group(3):
            results.skipped = int(match.group(3))
    return results


@register("test")
class TestStage(Stage):
    def run(self, ctx: PipelineContext) -> StageResult:
        command = self.stage_config.get("command", "pytest --tb=short -q")

        log.info("  Running: %s", command)
        result = run_command(command, cwd=ctx.project_root, timeout=600)

        output = result.stdout + result.stderr
        test_results = _parse_pytest_output(output)
        ctx.test_results = test_results

        summary = f"{test_results.passed} passed, {test_results.failed} failed, {test_results.skipped} skipped"
        success = result.ok and test_results.failed == 0
        return StageResult(success=success, summary=summary)
