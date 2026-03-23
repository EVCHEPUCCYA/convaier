"""Rich console UI for convaier."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

theme = Theme({
    "stage.ok": "bold green",
    "stage.fail": "bold red",
    "stage.skip": "dim",
    "stage.run": "bold cyan",
    "stage.name": "bold white",
    "timing": "dim cyan",
    "header": "bold magenta",
    "info": "dim",
    "warn": "yellow",
    "error": "bold red",
    "success": "bold green",
})

console = Console(theme=theme, stderr=True)

# Status icons
ICONS = {
    "ok": "[stage.ok]\u2713[/]",
    "fail": "[stage.fail]\u2717[/]",
    "skip": "[stage.skip]\u2014[/]",
    "run": "[stage.run]\u25b6[/]",
    "dry": "[stage.skip]\u25cb[/]",
    "wait": "[info]\u25cb[/]",
}


def print_header(project: str, stages: list[str]) -> None:
    pipeline_str = " [dim]\u2192[/] ".join(f"[bold]{s}[/]" for s in stages)
    console.print()
    console.print(Panel(
        f"[header]{project}[/]\n{pipeline_str}",
        title="[bold]convaier[/]",
        border_style="magenta",
        padding=(0, 2),
    ))
    console.print()


def print_stage_start(name: str) -> None:
    console.print(f"  {ICONS['run']} [stage.name]{name}[/]", end="")


def print_stage_result(success: bool, summary: str, duration: float) -> None:
    icon = ICONS["ok"] if success else ICONS["fail"]
    style = "stage.ok" if success else "stage.fail"
    console.print(f"  {icon} [{style}]{summary}[/] [timing]({duration:.1f}s)[/]")


def print_stage_skip(name: str) -> None:
    console.print(f"  {ICONS['skip']} [stage.skip]{name} (skipped)[/]")


def print_stage_dry(name: str) -> None:
    console.print(f"  {ICONS['dry']} [stage.skip]{name} (dry-run)[/]")


def print_stage_error(name: str, error: str) -> None:
    console.print(f"  {ICONS['fail']} [error]{name}: {error}[/]")


def print_detail(text: str, style: str = "info") -> None:
    console.print(f"    [{style}]{text}[/]")


def print_reports(paths: list) -> None:
    if not paths:
        return
    console.print()
    for p in paths:
        try:
            from pathlib import Path
            rel = Path(p).relative_to(Path.cwd())
            console.print(f"  [dim]Report:[/] {rel}")
        except ValueError:
            console.print(f"  [dim]Report:[/] {p}")


def print_summary(timings: dict[str, float], errors: list, total_time: float) -> None:
    console.print()
    if errors:
        console.print(Panel(
            f"[error]FAILED[/] — {len(errors)} error(s) in {total_time:.1f}s",
            border_style="red",
        ))
    else:
        console.print(Panel(
            f"[success]PASSED[/] in {total_time:.1f}s",
            border_style="green",
        ))


def print_timings_table(timings: dict[str, float]) -> None:
    if not timings:
        return
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Stage", style="bold")
    table.add_column("Time", justify="right", style="timing")
    for stage, t in timings.items():
        table.add_row(stage, f"{t:.1f}s")
    console.print(table)


def print_presets_table(presets: dict[str, dict]) -> None:
    table = Table(title="Language Presets", border_style="dim")
    table.add_column("Language", style="bold cyan")
    table.add_column("Lint", style="white")
    table.add_column("Security", style="white")
    table.add_column("Test", style="white")

    for name, preset in presets.items():
        lint_tools = ", ".join(
            t.get("name", "?") for t in preset.get("lint", {}).get("tools", [])
        ) or "-"
        sec_tools = ", ".join(
            t.get("name", "?") for t in preset.get("security", {}).get("tools", [])
        ) or "-"
        test_cmd = preset.get("test", {}).get("command", "-")
        table.add_row(name, lint_tools, sec_tools, test_cmd)

    console.print(table)


def print_check_ok(label: str, detail: str) -> None:
    console.print(f"  {ICONS['ok']} [bold]{label}[/] [dim]{detail}[/]")


def print_check_fail(label: str, detail: str) -> None:
    console.print(f"  {ICONS['fail']} [bold]{label}[/] [error]{detail}[/]")
