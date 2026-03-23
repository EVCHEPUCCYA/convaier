from __future__ import annotations

import json
import logging

from convaier.agent.client import agent_loop, create_client
from convaier.agent.prompt import build_metrics_prompt
from convaier.agent.tools import REVIEW_TOOLS
from convaier.context import FileMetrics, MetricsResult, PipelineContext
from convaier.stages import Stage, StageResult, register
from convaier.util.proc import run_command

log = logging.getLogger("convaier")


def _parse_radon_cc(output: str) -> dict[str, float]:
    """Parse radon cc JSON output -> {file: avg_complexity}."""
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, ValueError):
        return {}

    result = {}
    for filepath, blocks in data.items():
        if blocks:
            avg = sum(b.get("complexity", 0) for b in blocks) / len(blocks)
            result[filepath] = round(avg, 1)
        else:
            result[filepath] = 0.0
    return result


def _parse_radon_mi(output: str) -> dict[str, float]:
    """Parse radon mi JSON output -> {file: maintainability_index}."""
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, ValueError):
        return {}
    result = {}
    for f, v in data.items():
        if isinstance(v, dict):
            result[f] = round(v.get("mi", 0.0), 1)
        elif isinstance(v, (int, float)):
            result[f] = round(v, 1)
        else:
            result[f] = 0.0
    return result


def _parse_radon_raw(output: str) -> dict[str, int]:
    """Parse radon raw JSON output -> {file: loc}."""
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, ValueError):
        return {}
    return {f: v.get("loc", 0) for f, v in data.items() if isinstance(v, dict)}


def _parse_ai_recommendations(response: str) -> list[str]:
    recommendations = []
    for line in response.splitlines():
        line = line.strip()
        if line.startswith("RECOMMEND|"):
            parts = line.split("|", 1)
            if len(parts) == 2:
                recommendations.append(parts[1])
    return recommendations


@register("metrics")
class MetricsStage(Stage):
    def run(self, ctx: PipelineContext) -> StageResult:
        src_path = self.stage_config.get("src_path", ".")
        ai_review = self.stage_config.get("ai_review", False)

        # Run radon for cyclomatic complexity
        log.info("  Analyzing complexity...")
        cc_result = run_command(
            f"python -m radon cc {src_path} -j",
            cwd=ctx.project_root,
        )
        complexity_map = _parse_radon_cc(cc_result.stdout)

        # Run radon for maintainability index
        log.info("  Analyzing maintainability...")
        mi_result = run_command(
            f"python -m radon mi {src_path} -j",
            cwd=ctx.project_root,
        )
        mi_map = _parse_radon_mi(mi_result.stdout)

        # Run radon for raw metrics (LOC)
        raw_result = run_command(
            f"python -m radon raw {src_path} -j",
            cwd=ctx.project_root,
        )
        loc_map = _parse_radon_raw(raw_result.stdout)

        # Build per-file metrics
        all_files = set(complexity_map) | set(mi_map) | set(loc_map)
        file_metrics = []
        for f in sorted(all_files):
            file_metrics.append(FileMetrics(
                file=f,
                complexity=complexity_map.get(f, 0.0),
                maintainability=mi_map.get(f, 0.0),
                loc=loc_map.get(f, 0),
            ))

        # Compute averages
        metrics = MetricsResult(files=file_metrics)
        if file_metrics:
            metrics.avg_complexity = round(
                sum(fm.complexity for fm in file_metrics) / len(file_metrics), 1
            )
            metrics.avg_maintainability = round(
                sum(fm.maintainability for fm in file_metrics) / len(file_metrics), 1
            )
            metrics.total_loc = sum(fm.loc for fm in file_metrics)

        # Optional: coverage
        coverage_cmd = self.stage_config.get("coverage_command")
        if coverage_cmd:
            log.info("  Checking test coverage...")
            cov_result = run_command(coverage_cmd, cwd=ctx.project_root)
            # Try to parse coverage percentage from output
            for line in cov_result.stdout.splitlines():
                if "TOTAL" in line:
                    parts = line.split()
                    for part in reversed(parts):
                        pct = part.strip("%")
                        try:
                            metrics.coverage = float(pct)
                            break
                        except ValueError:
                            continue

        ctx.metrics_result = metrics

        # Log summary
        for fm in file_metrics:
            log.info("  %s: complexity=%.1f, MI=%.1f, LOC=%d",
                     fm.file, fm.complexity, fm.maintainability, fm.loc)

        # AI recommendations
        if ai_review and file_metrics:
            log.info("  AI analyzing metrics...")
            try:
                metrics_summary = "\n".join(
                    f"{fm.file}: complexity={fm.complexity}, maintainability={fm.maintainability}, LOC={fm.loc}"
                    for fm in file_metrics
                )
                prompt = build_metrics_prompt(
                    metrics_summary,
                    metrics.avg_complexity,
                    metrics.avg_maintainability,
                    metrics.total_loc,
                    metrics.coverage,
                )
                client = create_client(ctx.config.ollama)
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
                recommendations = _parse_ai_recommendations(response)
                metrics.ai_recommendations = recommendations
                for r in recommendations:
                    log.info("  [AI] %s", r)
            except Exception as e:
                log.error("  AI metrics analysis failed: %s", e)

        summary = (
            f"avg complexity={metrics.avg_complexity}, "
            f"avg MI={metrics.avg_maintainability}, "
            f"LOC={metrics.total_loc}"
        )
        if metrics.coverage is not None:
            summary += f", coverage={metrics.coverage}%"

        return StageResult(success=True, summary=summary)
