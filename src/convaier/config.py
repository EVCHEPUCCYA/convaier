from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class OllamaConfig:
    host: str = "http://localhost:11434"
    model: str = "qwen2.5-coder:3b"
    timeout: int = 120


@dataclass
class PipelineConfig:
    fail_fast: bool = True
    stages: list[str] = field(default_factory=lambda: [
        "commit", "lint", "review", "test", "build", "deploy",
    ])


@dataclass
class LintTool:
    command: str
    name: str


@dataclass
class ReportsConfig:
    output_dir: str = ".convaier/reports"
    formats: list[str] = field(default_factory=lambda: ["markdown", "json"])


@dataclass
class Config:
    project_name: str = "project"
    project_root: Path = field(default_factory=Path.cwd)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    stages: dict = field(default_factory=dict)
    reports: ReportsConfig = field(default_factory=ReportsConfig)


_OLLAMA_DEFAULTS = OllamaConfig()
_PIPELINE_DEFAULTS = PipelineConfig()
_REPORTS_DEFAULTS = ReportsConfig()


def _parse_ollama(raw: dict) -> OllamaConfig:
    return OllamaConfig(
        host=raw.get("host", _OLLAMA_DEFAULTS.host),
        model=raw.get("model", _OLLAMA_DEFAULTS.model),
        timeout=raw.get("timeout", _OLLAMA_DEFAULTS.timeout),
    )


def _parse_pipeline(raw: dict) -> PipelineConfig:
    return PipelineConfig(
        fail_fast=raw.get("fail_fast", True),
        stages=raw.get("stages", list(_PIPELINE_DEFAULTS.stages)),
    )


def _parse_reports(raw: dict) -> ReportsConfig:
    return ReportsConfig(
        output_dir=raw.get("output_dir", _REPORTS_DEFAULTS.output_dir),
        formats=raw.get("formats", list(_REPORTS_DEFAULTS.formats)),
    )


def load_config(path: Path) -> Config:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    project_root = path.parent.resolve()
    project = raw.get("project", {})

    return Config(
        project_name=project.get("name", project_root.name),
        project_root=project_root,
        ollama=_parse_ollama(raw.get("ollama", {})),
        pipeline=_parse_pipeline(raw.get("pipeline", {})),
        stages=raw.get("stages", {}),
        reports=_parse_reports(raw.get("reports", {})),
    )


EXAMPLE_CONFIG = """\
project:
  name: my-app

ollama:
  host: http://localhost:11434
  model: qwen2.5-coder:3b
  timeout: 120

pipeline:
  fail_fast: true
  stages:
    - commit
    - lint
    - review
    - test
    - build
    - deploy

stages:
  commit:
    diff_target: HEAD~1

  lint:
    tools:
      - command: ruff check .
        name: ruff

  review:
    focus:
      - security
      - performance
    max_files: 20
    max_diff_lines: 3000

  test:
    command: pytest --tb=short -q

  build:
    dockerfile: Dockerfile
    image_name: my-app
    tag: latest

  deploy:
    compose_file: docker-compose.yml
    service: app

reports:
  output_dir: .convaier/reports
  formats:
    - markdown
    - json
"""


def generate_example_config(path: Path) -> None:
    path.write_text(EXAMPLE_CONFIG, encoding="utf-8")
