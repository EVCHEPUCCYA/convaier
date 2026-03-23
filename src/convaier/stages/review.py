from __future__ import annotations

import logging
import re

from convaier.agent.client import agent_loop, create_client
from convaier.agent.prompt import build_review_prompt
from convaier.agent.tools import REVIEW_TOOLS
from convaier.context import PipelineContext, ReviewComment
from convaier.stages import Stage, StageResult, register
from convaier.ui import print_detail

log = logging.getLogger("convaier")

MAX_DIFF_LINES = 500
MAX_FILE_SIZE = 5_000


def _extract_file_diff(full_diff: str, filename: str) -> str:
    """Extract diff chunk for a specific file."""
    pattern = rf"(diff --git a/{re.escape(filename)} .*?)(?=diff --git a/|\Z)"
    match = re.search(pattern, full_diff, re.DOTALL)
    return match.group(1) if match else ""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... (truncated, {len(lines)} total)"


def _parse_review_response(response: str) -> list[ReviewComment]:
    comments = []
    for line in response.splitlines():
        line = line.strip()
        if line.startswith("COMMENT|"):
            parts = line.split("|", 3)
            if len(parts) >= 4:
                try:
                    comments.append(ReviewComment(
                        file=parts[1],
                        line=0,
                        severity=parts[2],
                        message=parts[3],
                    ))
                except (ValueError, IndexError):
                    continue
    return comments


def _review_single_file(
    filename: str,
    file_diff: str,
    file_content: str,
    focus: list[str],
    rag_context: str,
    security_summary: str,
    client,
    model: str,
    project_root,
    num_ctx: int = 4096,
) -> list[ReviewComment]:
    """Review a single file with AI."""
    prompt = build_review_prompt(
        diff=file_diff,
        file_contents={filename: file_content},
        lint_issues=[],
        focus=focus,
        rag_context=rag_context,
        security_summary=security_summary,
    )

    messages = [{"role": "user", "content": prompt}]
    response = agent_loop(
        client=client,
        model=model,
        messages=messages,
        tools=REVIEW_TOOLS,
        project_root=project_root,
        max_rounds=3,
        num_ctx=num_ctx,
    )
    return _parse_review_response(response)


@register("review")
class ReviewStage(Stage):
    def should_skip(self, ctx: PipelineContext) -> bool:
        return not ctx.git_diff

    def run(self, ctx: PipelineContext) -> StageResult:
        max_files = self.stage_config.get("max_files", 20)
        focus = self.stage_config.get("focus", [])
        use_rag = self.stage_config.get("use_rag", False)

        # Collect files to review
        code_files = []
        for f in ctx.changed_files[:max_files]:
            fpath = ctx.project_root / f
            if fpath.is_file() and fpath.suffix in (".py", ".js", ".ts", ".java", ".go", ".rs"):
                code_files.append(f)

        if not code_files:
            return StageResult(success=True, summary="No code files to review")

        # RAG context (one search for all)
        rag_context = ""
        if use_rag:
            try:
                from convaier.rag.search import build_rag_context
                rag_context = build_rag_context(
                    ctx.git_diff[:1000], ctx.changed_files, ctx.project_root, ctx.config.ollama,
                )
            except Exception:
                pass

        # Build security summary for AI context (task 4: pass security findings to review)
        security_summary = ""
        if ctx.security_issues:
            sec_lines = []
            for si in ctx.security_issues:
                sec_lines.append(f"[{si.severity}] {si.tool}: {si.file}:{si.line} — {si.message}")
            security_summary = "\n".join(sec_lines)

        client = create_client(ctx.config.ollama)
        all_comments: list[ReviewComment] = []
        reviewed = 0
        failed = 0

        for filename in code_files:
            fpath = ctx.project_root / filename

            # Read file content
            content = fpath.read_text(errors="replace")
            if len(content) > MAX_FILE_SIZE:
                content = content[:MAX_FILE_SIZE] + "\n... (truncated)"

            # Extract per-file diff
            file_diff = _extract_file_diff(ctx.git_diff, filename)
            if not file_diff:
                file_diff = f"(new or modified file, no diff extracted)\n"

            file_diff = _truncate(file_diff, MAX_DIFF_LINES)

            # Per-file security summary
            file_sec_lines = [
                f"[{si.severity}] {si.tool}: {si.file}:{si.line} — {si.message}"
                for si in ctx.security_issues if si.file.endswith(filename)
            ]
            file_security = "\n".join(file_sec_lines) if file_sec_lines else security_summary

            print_detail(f"reviewing {filename}...")

            try:
                comments = _review_single_file(
                    filename, file_diff, content, focus, rag_context,
                    file_security,
                    client, ctx.config.ollama.model, ctx.project_root,
                    num_ctx=ctx.config.ollama.num_ctx,
                )
                all_comments.extend(comments)
                reviewed += 1

                if comments:
                    for c in comments:
                        print_detail(f"[{c.severity}] {c.file} — {c.message}", "warn")
                else:
                    print_detail(f"{filename}: OK", "info")

            except Exception as e:
                failed += 1
                print_detail(f"{filename}: failed ({e})", "error")

        ctx.review_comments = all_comments

        parts = [f"{reviewed} file(s) reviewed"]
        if all_comments:
            parts.append(f"{len(all_comments)} comment(s)")
        if failed:
            parts.append(f"{failed} failed")

        return StageResult(success=True, summary=", ".join(parts))
