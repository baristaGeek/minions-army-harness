"""Pipeline step implementation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from minions_army.application.services.orchestration_service import (
    OrchestrationResult,
    PipelineContext,
)
from minions_army.core.runtime import orchestrator_runtime as runtime
from minions_army.core.runtime.logging import log_event

logger = logging.getLogger("minions_army.core.runtime.orchestrator_runtime")


@dataclass
class InitializeWorkspaceStep:
    name: str = "initialize-workspace"
    skip: bool = False

    def execute(self, context: PipelineContext) -> None:
        def action() -> None:
            repo_root = Path("/source/repo")
            repo_root.mkdir(parents=True, exist_ok=True)
            if any(repo_root.iterdir()):
                raise SystemExit(f"{repo_root} must be empty before cloning")
            work_branch = (
                f"{context.request.feature_branch.rstrip('/')}_{context.request.container_name}_"
                f"{uuid4().hex[:12]}"
            )
            context.result = OrchestrationResult(repository_path=repo_root, work_branch=work_branch)
            log_event(
                logger,
                logging.INFO,
                "workspace.initialized",
                repository_path=repo_root,
                work_branch=work_branch,
            )

        runtime._run_step_with_logging(context, self.name, self.skip, action)
