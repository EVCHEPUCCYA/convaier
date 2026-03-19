from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from convaier.config import Config


@dataclass
class LintIssue:
    tool: str
    file: str
    line: int
    message: str
    severity: str = "warning"


@dataclass
class ReviewComment:
    file: str
    line: int
    message: str
    severity: str = "info"


@dataclass
class TestResults:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration: float = 0.0
    output: str = ""


@dataclass
class BuildResult:
    image: str = ""
    tag: str = ""
    success: bool = False
    duration: float = 0.0
    output: str = ""


@dataclass
class DeployResult:
    service: str = ""
    success: bool = False
    output: str = ""


@dataclass
class StageError:
    stage: str
    error: str


@dataclass
class PipelineContext:
    project_root: Path
    config: Config

    # commit stage
    git_diff: str = ""
    changed_files: list[str] = field(default_factory=list)

    # lint stage
    lint_results: list[LintIssue] = field(default_factory=list)
    lint_passed: bool = True

    # review stage
    review_comments: list[ReviewComment] = field(default_factory=list)

    # test stage
    test_results: TestResults | None = None

    # build stage
    build_result: BuildResult | None = None

    # deploy stage
    deploy_result: DeployResult | None = None

    # errors & timings
    errors: list[StageError] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
