from __future__ import annotations

import json
import logging

from convaier.agent.client import agent_loop, create_client
from convaier.agent.prompt import build_security_prompt
from convaier.agent.tools import REVIEW_TOOLS
from convaier.context import PipelineContext, ReviewComment, SecurityIssue
from convaier.stages import Stage, StageResult, register
from convaier.util.proc import run_command

log = logging.getLogger("convaier")


def _parse_bandit_json(output: str) -> list[SecurityIssue]:
    issues = []
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, ValueError):
        return issues

    for result in data.get("results", []):
        severity = result.get("issue_severity", "MEDIUM").lower()
        issues.append(SecurityIssue(
            tool="bandit",
            file=result.get("filename", ""),
            line=result.get("line_number", 0),
            severity=severity,
            message=result.get("issue_text", ""),
            cwe=str(result.get("issue_cwe", {}).get("id", "")),
        ))
    return issues


def _parse_pip_audit_json(output: str) -> list[SecurityIssue]:
    issues = []
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, ValueError):
        return issues

    vulnerabilities = data if isinstance(data, list) else data.get("dependencies", [])
    for dep in vulnerabilities:
        for vuln in dep.get("vulns", []):
            issues.append(SecurityIssue(
                tool="pip-audit",
                file="requirements",
                line=0,
                severity="high",
                message=f"{dep.get('name', '?')}=={dep.get('version', '?')}: {vuln.get('id', '')} — {vuln.get('description', '')}",
                cwe="",
            ))
    return issues


_PARSERS = {
    "bandit": _parse_bandit_json,
    "pip-audit": _parse_pip_audit_json,
}


def _parse_ai_response(response: str) -> list[ReviewComment]:
    comments = []
    for line in response.splitlines():
        line = line.strip()
        if line.startswith("SECURITY|"):
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


@register("security")
class SecurityStage(Stage):
    def run(self, ctx: PipelineContext) -> StageResult:
        tools = self.stage_config.get("tools", [
            {"command": "python -m bandit -r . -f json --quiet", "name": "bandit"},
        ])
        ai_review = self.stage_config.get("ai_review", False)
        fail_on_critical = self.stage_config.get("fail_on_critical", True)

        all_issues: list[SecurityIssue] = []

        # Run security tools
        for tool_cfg in tools:
            name = tool_cfg.get("name", "unknown")
            command = tool_cfg.get("command", "")
            if not command:
                continue

            log.info("  Running %s: %s", name, command)
            result = run_command(command, cwd=ctx.project_root)

            parser = _PARSERS.get(name)
            if parser:
                issues = parser(result.stdout)
            else:
                # Generic: try JSON, fall back to text
                try:
                    issues = _parse_bandit_json(result.stdout)
                except Exception:
                    issues = []

            all_issues.extend(issues)

            if issues:
                log.warning("  %s: %d issue(s)", name, len(issues))
            else:
                log.info("  %s: OK", name)

        ctx.security_issues = all_issues

        # AI analysis — per-file
        if ai_review and ctx.git_diff:
            from convaier.ui import print_detail

            # RAG context (one search for all)
            rag_context = ""
            if self.stage_config.get("use_rag", False):
                try:
                    from convaier.rag.search import build_rag_context
                    rag_context = build_rag_context(
                        ctx.git_diff[:1000], ctx.changed_files, ctx.project_root, ctx.config.ollama,
                    )
                except Exception:
                    pass

            client = create_client(ctx.config.ollama)
            all_ai_comments: list[ReviewComment] = []

            # Filter: only code files with known issues or changed
            code_files = [
                f for f in ctx.changed_files[:20]
                if (ctx.project_root / f).is_file()
                and (ctx.project_root / f).suffix in (".py", ".js", ".ts", ".java", ".go")
            ]

            for filename in code_files:
                fpath = ctx.project_root / filename
                content = fpath.read_text(errors="replace")[:5_000]

                # Issues for this file
                file_issues = [i for i in all_issues if i.file.endswith(filename)]
                tool_summary = "\n".join(
                    f"[{i.severity}] {i.tool}: {i.file}:{i.line} — {i.message}"
                    for i in file_issues
                )

                print_detail(f"AI scanning {filename}...")

                try:
                    prompt = build_security_prompt(
                        tool_summary, "", {filename: content}, rag_context,
                    )
                    messages = [{"role": "user", "content": prompt}]
                    response = agent_loop(
                        client=client,
                        model=ctx.config.ollama.model,
                        messages=messages,
                        tools=REVIEW_TOOLS,
                        project_root=ctx.project_root,
                        max_rounds=3,
                        num_ctx=ctx.config.ollama.num_ctx,
                    )
                    comments = _parse_ai_response(response)
                    all_ai_comments.extend(comments)

                    if comments:
                        for c in comments:
                            print_detail(f"[AI/{c.severity}] {c.file} — {c.message}", "warn")
                    else:
                        print_detail(f"{filename}: OK")

                except Exception as e:
                    print_detail(f"{filename}: AI failed ({e})", "error")

            ctx.security_ai_comments = all_ai_comments

        # Determine result
        total = len(all_issues) + len(ctx.security_ai_comments)
        has_critical = any(
            i.severity in ("critical", "high") for i in all_issues
        ) or any(
            c.severity == "critical" for c in ctx.security_ai_comments
        )

        success = not (has_critical and fail_on_critical)
        summary = f"{total} issue(s) found" if total else "No security issues"
        return StageResult(success=success, summary=summary)
