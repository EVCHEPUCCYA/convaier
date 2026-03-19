from __future__ import annotations

from pathlib import Path

from convaier.util.proc import RunResult, run_command


def get_diff(cwd: Path, target: str = "HEAD~1") -> RunResult:
    return run_command(["git", "diff", target], cwd=cwd)


def get_staged_diff(cwd: Path) -> RunResult:
    return run_command(["git", "diff", "--cached"], cwd=cwd)


def get_changed_files(cwd: Path, target: str = "HEAD~1") -> list[str]:
    result = run_command(["git", "diff", "--name-only", target], cwd=cwd)
    if not result.ok:
        return []
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def get_log(cwd: Path, count: int = 5) -> str:
    result = run_command(
        ["git", "log", f"-{count}", "--oneline"],
        cwd=cwd,
    )
    return result.stdout if result.ok else ""
