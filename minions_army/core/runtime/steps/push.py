"""Pipeline step implementation."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from minions_army.application.services.orchestration_service import (
    PipelineContext,
)
from minions_army.core.runtime import orchestrator_runtime as runtime
from minions_army.core.runtime.logging import log_event

logger = logging.getLogger("minions_army.core.runtime.orchestrator_runtime")


@runtime._wrap_step_execute
@dataclass
class PushStep:
    name: str = "push"
    skip: bool = False

    def execute(self, context: PipelineContext) -> None:
        result = context.require_result()
        log_event(logger, logging.INFO, "git.push.prepared", work_branch=result.work_branch)
        runtime.run_command(
            ["git", "push", "-u", "origin", result.work_branch], result.repository_path
        )
