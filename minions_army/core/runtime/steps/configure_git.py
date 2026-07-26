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
class ConfigureGitStep:
    name: str = "git-config"
    skip: bool = False

    def execute(self, context: PipelineContext) -> None:
        def action() -> None:
            result = context.require_result()
            log_event(
                logger,
                logging.INFO,
                "git.config.prepared",
                repository_path=result.repository_path,
                author_name=context.request.git_author_name,
                author_email=context.request.git_author_email,
            )
            runtime.run_command(
                [
                    "git",
                    "config",
                    "--global",
                    "--add",
                    "safe.directory",
                    str(result.repository_path),
                ],
                result.repository_path,
            )
            runtime.run_command(
                ["git", "config", "user.name", context.request.git_author_name],
                result.repository_path,
            )
            runtime.run_command(
                ["git", "config", "user.email", context.request.git_author_email],
                result.repository_path,
            )

        runtime._run_step_with_logging(context, self.name, self.skip, action)
