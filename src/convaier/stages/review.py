from __future__ import annotations

import logging

from convaier.agent.client import agent_loop, create_client
from convaier.agent.prompt import build_review_prompt
from convaier.agent.tools import REVIEW_TOOLS
from convaier.context import PipelineContext, ReviewComment
from convaier.stages import Stage, StageResult, register

log = logging.getLogger("convaier")

MAX_DIFF_LINES = 3000
MAX_FILE_SIZE = 10_000


def _truncate_diff(diff: str, max_lines: int) -> str:
    lines = diff.splitlines()
    if len(lines) <= max_lines:
        return diff
    return "\n".join(lines[:max_lines]) + f"\n... (truncated, {len(lines)} total lines)"


def _parse_review_response(response: str) -> list[ReviewComment]:
    comments = []
    for line in response.splitlines():
        line = line.strip()
        if line.startswith("COMMENT|"):
            parts = line.split("|", 4)
            if len(parts) >= 5:
                try:
                    comments.append(ReviewComment(
                        file=parts[1],
                        line=int(parts[2]) if parts[2].isdigit() else 0,
                        severity=parts[3],
                        message=parts[4],
                    ))
                except (ValueError, IndexError):
                    continue
    return comments


@register("review")
class ReviewStage(Stage):
    def should_skip(self, ctx: PipelineContext) -> bool:
        if not ctx.git_diff:
            return True
        return False

    def run(self, ctx: PipelineContext) -> StageResult:
        max_files = self.stage_config.get("max_files", 20)
        max_diff_lines = self.stage_config.get("max_diff_lines", MAX_DIFF_LINES)
        focus = self.stage_config.get("focus", [])

        diff = _truncate_diff(ctx.git_diff, max_diff_lines)

        # Read changed file contents
        file_contents: dict[str, str] = {}
        for f in ctx.changed_files[:max_files]:
            fpath = ctx.project_root / f
            if fpath.is_file():
                content = fpath.read_text(errors="replace")
                if len(content) > MAX_FILE_SIZE:
                    content = content[:MAX_FILE_SIZE] + "\n... (truncated)"
                file_contents[f] = content

        prompt = build_review_prompt(diff, file_contents, ctx.lint_results, focus)

        # Call LLM
        try:
            client = create_client(ctx.config.ollama)
            messages = [{"role": "user", "content": prompt}]
            response = agent_loop(
                client=client,
                model=ctx.config.ollama.model,
                messages=messages,
                tools=REVIEW_TOOLS,
                project_root=ctx.project_root,
                max_rounds=5,
            )
        except Exception as e:
            log.error("  Ollama error: %s", e)
            return StageResult(success=False, summary=f"AI review failed: {e}")

        comments = _parse_review_response(response)
        ctx.review_comments = comments

        if not comments:
            return StageResult(success=True, summary="No issues found by AI")

        for c in comments:
            log.info("  [%s] %s:%d — %s", c.severity, c.file, c.line, c.message)

        return StageResult(success=True, summary=f"{len(comments)} comment(s)")
