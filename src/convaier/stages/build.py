from __future__ import annotations

import logging
import time

from convaier.context import BuildResult, PipelineContext
from convaier.stages import Stage, StageResult, register
from convaier.util.docker import build_image

log = logging.getLogger("convaier")


@register("build")
class BuildStage(Stage):
    def should_skip(self, ctx: PipelineContext) -> bool:
        return bool(ctx.errors)

    def run(self, ctx: PipelineContext) -> StageResult:
        dockerfile = self.stage_config.get("dockerfile", "Dockerfile")
        image_name = self.stage_config.get("image_name", ctx.config.project_name)
        tag = self.stage_config.get("tag", "latest")

        log.info("  Building %s:%s from %s", image_name, tag, dockerfile)
        t0 = time.monotonic()
        result = build_image(ctx.project_root, dockerfile, image_name, tag)
        duration = time.monotonic() - t0

        ctx.build_result = BuildResult(
            image=image_name,
            tag=tag,
            success=result.ok,
            duration=duration,
            output=result.stdout + result.stderr,
        )

        if not result.ok:
            log.error("  Build failed:\n%s", result.stderr[-500:])
            return StageResult(success=False, summary=f"Build failed ({duration:.1f}s)")

        return StageResult(success=True, summary=f"{image_name}:{tag} built ({duration:.1f}s)")
