"""Pipeline step implementation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from minions_army.application.services.orchestration_service import (
    OrchestrationResult,
    PipelineContext,
)
from minions_army.core.runtime import orchestrator_runtime as runtime
from minions_army.core.runtime.logging import log_event

logger = logging.getLogger("minions_army.core.runtime.orchestrator_runtime")


@dataclass
class HelloWorldStep:
    name: str = "helloworld"
    skip: bool = False

    def execute(self, context: PipelineContext) -> None:
        def action() -> None:
            log_event(logger, logging.INFO, "HelloWorld")
            # SubprocessPipelineRunner requires a result at the end of the
            # pipeline; this step never clones a repository, so use a placeholder.
            context.result = OrchestrationResult(
                repository_path=Path("."), work_branch="helloworld"
            )

        runtime._run_step_with_logging(context, self.name, self.skip, action)
