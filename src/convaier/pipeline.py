from __future__ import annotations

import logging
import time

from convaier.config import Config
from convaier.context import PipelineContext, StageError
from convaier.stages import STAGE_REGISTRY

log = logging.getLogger("convaier")


def run_pipeline(
    config: Config,
    stage_filter: list[str] | None = None,
    dry_run: bool = False,
) -> PipelineContext:
    ctx = PipelineContext(project_root=config.project_root, config=config)
    stage_names = stage_filter or config.pipeline.stages

    log.info("Pipeline: %s", " → ".join(stage_names))

    for name in stage_names:
        stage_cls = STAGE_REGISTRY.get(name)
        if not stage_cls:
            log.error("Unknown stage: %s (skipping)", name)
            continue

        stage = stage_cls(stage_config=config.stages.get(name, {}))

        if stage.should_skip(ctx):
            log.info("[SKIP] %s", name)
            continue

        if dry_run:
            log.info("[DRY-RUN] %s", name)
            continue

        log.info("[START] %s", name)
        t0 = time.monotonic()

        try:
            result = stage.run(ctx)
            ctx.timings[name] = time.monotonic() - t0

            status = "OK" if result.success else "FAIL"
            log.info("[%s] %s — %s (%.1fs)", status, name, result.summary, ctx.timings[name])

            if not result.success and config.pipeline.fail_fast:
                log.error("Fail-fast: stopping pipeline.")
                break
        except Exception as e:
            ctx.timings[name] = time.monotonic() - t0
            ctx.errors.append(StageError(stage=name, error=str(e)))
            log.exception("[ERROR] %s", name)
            if config.pipeline.fail_fast:
                break

    # Generate reports
    from convaier.report import generate_reports

    paths = generate_reports(ctx)
    for p in paths:
        log.info("Report: %s", p)

    return ctx
