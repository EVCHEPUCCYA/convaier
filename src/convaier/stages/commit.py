from __future__ import annotations

import logging

from convaier.context import PipelineContext
from convaier.stages import Stage, StageResult, register
from convaier.util.git import get_changed_files, get_diff

log = logging.getLogger("convaier")


@register("commit")
class CommitStage(Stage):
    def run(self, ctx: PipelineContext) -> StageResult:
        target = self.stage_config.get("diff_target", "HEAD~1")

        diff_result = get_diff(ctx.project_root, target)
        if not diff_result.ok:
            return StageResult(success=False, summary=f"git diff failed: {diff_result.stderr}")

        ctx.git_diff = diff_result.stdout
        ctx.changed_files = get_changed_files(ctx.project_root, target)

        if not ctx.changed_files:
            return StageResult(success=True, summary="No changes detected")

        log.info("Changed files (%d): %s", len(ctx.changed_files), ", ".join(ctx.changed_files[:10]))
        return StageResult(
            success=True,
            summary=f"{len(ctx.changed_files)} file(s) changed",
        )
