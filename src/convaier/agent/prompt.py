from __future__ import annotations

from convaier.context import LintIssue


def build_review_prompt(
    diff: str,
    file_contents: dict[str, str],
    lint_issues: list[LintIssue],
    focus: list[str] | None = None,
    rag_context: str = "",
    security_summary: str = "",
) -> str:
    parts = [
        "You are a code reviewer. Analyze the following code changes and provide feedback.",
        "",
        "RULES:",
        "- For each issue, output EXACTLY one line in this format:",
        "  COMMENT|<file_path>|<severity>|<description>",
        "- <severity> is one of: critical, warning, info, suggestion",
        "- <file_path> must be the actual file path from the diff",
        "- Do NOT include line numbers — just describe the problem clearly.",
        "- If no issues, output: NO_ISSUES",
        "- Do NOT repeat issues already found by security tools (listed below).",
        "- Do NOT output anything else — no explanations, no markdown, no headers.",
        "",
        "EXAMPLE OUTPUT:",
        "COMMENT|app.py|critical|SQL injection: user input is interpolated directly into SQL query via f-string in search()",
        "COMMENT|utils.py|warning|Writing to /tmp/app.log without sanitization may allow log injection",
        "",
    ]

    if focus:
        parts.append(f"Focus areas: {', '.join(focus)}")
        parts.append("")

    if security_summary:
        parts.append("== Security Issues (already found by tools — do NOT repeat these) ==")
        parts.append(security_summary)
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

    if rag_context:
        parts.append(rag_context)
        parts.append("")

    return "\n".join(parts)


def build_security_prompt(
    tool_results: str,
    diff: str,
    file_contents: dict[str, str],
    rag_context: str = "",
) -> str:
    parts = [
        "You are a security auditor. Analyze the code for vulnerabilities that static tools may miss.",
        "",
        "RULES:",
        "- For each issue, output EXACTLY one line in this format:",
        "  SECURITY|<file_path>|<severity>|<description>",
        "- <severity> is one of: critical, warning, info",
        "- Do NOT include line numbers — just describe the problem clearly, mention the function name.",
        "- If no additional issues, output: NO_ISSUES",
        "- Do NOT repeat issues already found by tools below.",
        "- Focus on: SQL injection, XSS, command injection, path traversal, hardcoded secrets, insecure crypto, SSRF.",
        "",
        "EXAMPLE OUTPUT:",
        "SECURITY|app.py|critical|User input passed directly to os.system() in run_cmd() — command injection",
        "SECURITY|config.py|warning|API key hardcoded in source code",
        "",
    ]

    if tool_results:
        parts.append("== Issues Already Found by Tools ==")
        parts.append(tool_results)
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

    if rag_context:
        parts.append(rag_context)
        parts.append("")

    return "\n".join(parts)


def build_metrics_prompt(
    metrics_summary: str,
    avg_complexity: float,
    avg_maintainability: float,
    total_loc: int,
    coverage: float | None,
) -> str:
    parts = [
        "You are a code quality analyst. Analyze the following code metrics and provide recommendations.",
        "",
        "RULES:",
        "- For each recommendation, output EXACTLY one line in this format:",
        "  RECOMMEND|<recommendation>",
        "- Focus on: high complexity functions that need refactoring, low maintainability files, insufficient test coverage.",
        "- Be specific — name files and suggest concrete actions.",
        "- Output 3-5 recommendations maximum.",
        "- If code quality is good, output: NO_ISSUES",
        "",
        "REFERENCE:",
        "- Cyclomatic complexity: 1-5 = simple, 6-10 = moderate, 11+ = complex (needs refactoring)",
        "- Maintainability index: 0-9 = low, 10-19 = moderate, 20+ = good",
        "",
        f"== Summary ==",
        f"Average complexity: {avg_complexity}",
        f"Average maintainability index: {avg_maintainability}",
        f"Total LOC: {total_loc}",
    ]

    if coverage is not None:
        parts.append(f"Test coverage: {coverage}%")

    parts.extend([
        "",
        "== Per-File Metrics ==",
        metrics_summary,
    ])

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
