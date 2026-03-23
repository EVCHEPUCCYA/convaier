from __future__ import annotations

import logging
import time

from convaier.config import Config
from convaier.context import PipelineContext, StageError
from convaier.stages import STAGE_REGISTRY
from convaier.ui import (
    print_detail,
    print_header,
    print_reports,
    print_stage_dry,
    print_stage_error,
    print_stage_result,
    print_stage_skip,
    print_summary,
)

log = logging.getLogger("convaier")


def run_pipeline(
    config: Config,
    stage_filter: list[str] | None = None,
    dry_run: bool = False,
) -> PipelineContext:
    ctx = PipelineContext(project_root=config.project_root, config=config)
    stage_names = stage_filter or config.pipeline.stages

    print_header(config.project_name, stage_names)

    pipeline_t0 = time.monotonic()

    for name in stage_names:
        stage_cls = STAGE_REGISTRY.get(name)
        if not stage_cls:
            print_stage_error(name, "unknown stage")
            continue

        stage = stage_cls(stage_config=config.stages.get(name, {}))

        if stage.should_skip(ctx):
            print_stage_skip(name)
            continue

        if dry_run:
            print_stage_dry(name)
            continue

        t0 = time.monotonic()

        try:
            result = stage.run(ctx)
            ctx.timings[name] = time.monotonic() - t0

            print_stage_result(result.success, f"{name} — {result.summary}", ctx.timings[name])

            if not result.success and config.pipeline.fail_fast:
                print_detail("Fail-fast: stopping pipeline", "error")
                break
        except Exception as e:
            ctx.timings[name] = time.monotonic() - t0
            ctx.errors.append(StageError(stage=name, error=str(e)))
            print_stage_error(name, str(e))
            if config.pipeline.fail_fast:
                break

    total_time = time.monotonic() - pipeline_t0

    # Generate reports
    from convaier.report import generate_reports
    paths = generate_reports(ctx)

    print_summary(ctx.timings, ctx.errors, total_time)
    print_reports(paths)

    return ctx
