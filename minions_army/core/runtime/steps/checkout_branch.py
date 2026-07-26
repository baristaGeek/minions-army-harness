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


@dataclass
class CheckoutBranchStep:
    name: str = "checkout"
    skip: bool = False

    def execute(self, context: PipelineContext) -> None:
        def action() -> None:
            result = context.require_result()
            log_event(logger, logging.INFO, "git.checkout.prepared", work_branch=result.work_branch)
            runtime.run_command(
                ["git", "checkout", "-b", result.work_branch], result.repository_path
            )

        runtime._run_step_with_logging(context, self.name, self.skip, action)
