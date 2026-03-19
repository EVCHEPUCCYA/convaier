from __future__ import annotations

import logging

from convaier.context import LintIssue, PipelineContext
from convaier.stages import Stage, StageResult, register
from convaier.util.proc import run_command

log = logging.getLogger("convaier")


def _parse_lint_output(tool_name: str, stdout: str) -> list[LintIssue]:
    issues = []
    for line in stdout.splitlines():
        # Common format: file.py:10:5: E001 message
        parts = line.split(":", 3)
        if len(parts) >= 4:
            try:
                issues.append(LintIssue(
                    tool=tool_name,
                    file=parts[0].strip(),
                    line=int(parts[1].strip()),
                    message=parts[3].strip() if len(parts) > 3 else parts[2].strip(),
                ))
            except (ValueError, IndexError):
                continue
    return issues


@register("lint")
class LintStage(Stage):
    def run(self, ctx: PipelineContext) -> StageResult:
        tools = self.stage_config.get("tools", [])
        if not tools:
            return StageResult(success=True, summary="No lint tools configured")

        fail_on_error = self.stage_config.get("fail_on_error", True)
        all_issues: list[LintIssue] = []
        any_failed = False

        for tool_cfg in tools:
            name = tool_cfg.get("name", "unknown")
            command = tool_cfg.get("command", "")
            if not command:
                continue

            log.info("  Running %s: %s", name, command)
            result = run_command(command, cwd=ctx.project_root)

            issues = _parse_lint_output(name, result.stdout)
            all_issues.extend(issues)

            if not result.ok:
                any_failed = True
                log.warning("  %s: %d issue(s)", name, len(issues))
            else:
                log.info("  %s: OK", name)

        ctx.lint_results = all_issues
        ctx.lint_passed = not any_failed

        success = not any_failed or not fail_on_error
        summary = f"{len(all_issues)} issue(s) from {len(tools)} tool(s)"
        return StageResult(success=success, summary=summary)
