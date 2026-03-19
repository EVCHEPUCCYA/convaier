from __future__ import annotations

import logging

from convaier.context import DeployResult, PipelineContext
from convaier.stages import Stage, StageResult, register
from convaier.util.docker import compose_up

log = logging.getLogger("convaier")


@register("deploy")
class DeployStage(Stage):
    def should_skip(self, ctx: PipelineContext) -> bool:
        if ctx.errors:
            return True
        if ctx.build_result and not ctx.build_result.success:
            return True
        return False

    def run(self, ctx: PipelineContext) -> StageResult:
        compose_file = self.stage_config.get("compose_file", "docker-compose.yml")
        service = self.stage_config.get("service")

        log.info("  Deploying via %s", compose_file)
        result = compose_up(ctx.project_root, compose_file, service)

        ctx.deploy_result = DeployResult(
            service=service or "all",
            success=result.ok,
            output=result.stdout + result.stderr,
        )

        if not result.ok:
            log.error("  Deploy failed:\n%s", result.stderr[-500:])
            return StageResult(success=False, summary=f"Deploy failed: {result.stderr[:100]}")

        return StageResult(success=True, summary=f"Service '{service or 'all'}' deployed")
