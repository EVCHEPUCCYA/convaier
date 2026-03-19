from __future__ import annotations

from convaier.context import LintIssue


def build_review_prompt(
    diff: str,
    file_contents: dict[str, str],
    lint_issues: list[LintIssue],
    focus: list[str] | None = None,
) -> str:
    parts = [
        "You are a code reviewer. Analyze the following code changes and provide feedback.",
        "",
        "RULES:",
        "- For each issue, output EXACTLY one line in this format:",
        "  COMMENT|<file_path>|<line_number>|<severity>|<description>",
        "- <severity> is one of: critical, warning, info, suggestion",
        "- <file_path> must be the actual file path from the diff",
        "- <line_number> must be a real line number",
        "- If no issues, output: NO_ISSUES",
        "- Do NOT output anything else — no explanations, no markdown, no headers.",
        "",
        "EXAMPLE OUTPUT:",
        "COMMENT|app.py|26|critical|SQL injection: user input is interpolated directly into SQL query",
        "COMMENT|utils.py|14|warning|Writing to /tmp/app.log without sanitization may allow log injection",
        "",
    ]

    if focus:
        parts.append(f"Focus areas: {', '.join(focus)}")
        parts.append("")

    if lint_issues:
        parts.append("== Lint Issues (already found by tools) ==")
        for issue in lint_issues[:20]:
            parts.append(f"  {issue.tool}: {issue.file}:{issue.line} — {issue.message}")
        parts.append("")

    parts.append("== Git Diff ==")
    parts.append(diff)
    parts.append("")

    if file_contents:
        parts.append("== Changed Files (full content) ==")
        for path, content in file_contents.items():
            parts.append(f"--- {path} ---")
            parts.append(content)
            parts.append("")

    return "\n".join(parts)


def build_test_analysis_prompt(test_output: str, diff: str) -> str:
    return "\n".join([
        "You are a test analyst. The following test run has failures.",
        "Analyze the test output and the recent code changes to explain the likely cause.",
        "Respond in this format:",
        "ANALYSIS|test_name|likely_cause|suggested_fix",
        "",
        "== Test Output ==",
        test_output,
        "",
        "== Recent Changes ==",
        diff,
    ])
