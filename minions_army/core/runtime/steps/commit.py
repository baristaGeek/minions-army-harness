"""Pipeline step implementation."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from minions_army.application.services.orchestration_service import (
    AgentOutput,
    PipelineContext,
)
from minions_army.core.runtime import orchestrator_runtime as runtime
from minions_army.core.runtime.logging import log_event

logger = logging.getLogger("minions_army.core.runtime.orchestrator_runtime")


@runtime._wrap_step_execute
@dataclass
class CommitStep:
    name: str = "commit"
    skip: bool = False

    def execute(self, context: PipelineContext) -> None:
        result = context.require_result()
        outputs: dict[str, AgentOutput] = context.agent_outputs or {}
        implementation = outputs.get("implementation") or outputs.get("apply")
        if implementation is None:
            raise SystemExit("Implementation stage did not produce a response")
        commit_message = implementation.get("commit_message") or implementation.get("summary")
        if not commit_message:
            commit_message = "Apply requested change"
        runtime.run_command(["git", "add", "-A"], result.repository_path)
        # Guard: pipeline scaffolding (constitution, openspec/, .claude/, prompt &
        # output dumps) must never land in a product PR, even when it slips past
        # .gitignore because the file was already tracked and got overwritten.
        runtime._unstage_pipeline_artifacts(result.repository_path)
        staged_paths = runtime._staged_paths(result.repository_path)
        if not staged_paths:
            log_event(logger, logging.WARNING, "git.commit.skipped", reason="no_file_changes")
            runtime.post_slack("⚠️ The agent produced no file changes, so there's nothing to ship.")
            raise SystemExit("No changes to commit")
        log_event(
            logger,
            logging.INFO,
            "git.commit.prepared",
            work_branch=result.work_branch,
            commit_message=commit_message,
            staged_paths=staged_paths,
        )
        runtime.run_command(["git", "commit", "-m", commit_message], result.repository_path)
