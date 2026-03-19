from __future__ import annotations

from pathlib import Path

from convaier.util.proc import RunResult, run_command


def build_image(
    cwd: Path,
    dockerfile: str = "Dockerfile",
    image_name: str = "app",
    tag: str = "latest",
) -> RunResult:
    return run_command(
        ["docker", "build", "-f", dockerfile, "-t", f"{image_name}:{tag}", "."],
        cwd=cwd,
        timeout=600,
    )


def compose_up(
    cwd: Path,
    compose_file: str = "docker-compose.yml",
    service: str | None = None,
) -> RunResult:
    cmd = ["docker", "compose", "-f", compose_file, "up", "-d"]
    if service:
        cmd.append(service)
    return run_command(cmd, cwd=cwd, timeout=120)


def compose_down(
    cwd: Path,
    compose_file: str = "docker-compose.yml",
) -> RunResult:
    return run_command(
        ["docker", "compose", "-f", compose_file, "down"],
        cwd=cwd,
        timeout=60,
    )
