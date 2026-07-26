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
class CloneRepositoryStep:
    name: str = "clone"
    skip: bool = False

    def execute(self, context: PipelineContext) -> None:
        def action() -> None:
            result = context.require_result()
            repository_url = runtime.resolve_repository_url(context.request.repository_name)
            log_event(
                logger,
                logging.INFO,
                "repository.clone.prepared",
                repository=context.request.repository_name,
                repository_url=repository_url,
                base_branch=context.request.base_branch,
                destination=result.repository_path,
            )
            runtime.configure_git_auth(context.request.github_token)
            runtime.run_command(
                [
                    "git",
                    "clone",
                    "--branch",
                    context.request.base_branch,
                    "--single-branch",
                    repository_url,
                    ".",
                ],
                result.repository_path,
            )

        runtime._run_step_with_logging(context, self.name, self.skip, action)
