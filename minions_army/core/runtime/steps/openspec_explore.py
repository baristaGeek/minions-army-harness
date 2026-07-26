"""Pipeline step implementation."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from minions_army.application.services.orchestration_service import (
    PipelineContext,
)
from minions_army.core.runtime import agent_execution
from minions_army.core.runtime import orchestrator_runtime as runtime

logger = logging.getLogger("minions_army.core.runtime.orchestrator_runtime")


@dataclass
class OpenspecExploreStep:
    name: str = "openspec-explore"
    skip: bool = False

    def execute(self, context: PipelineContext) -> None:
        def action() -> None:
            result = context.require_result()
            prompt = agent_execution._build_agent_prompt(context, result, "explore")
            session_id, resume_session = agent_execution._resolve_agent_session(context, "explore")
            raw_output = agent_execution._execute_agent_strategy(
                prompt=prompt,
                cwd=result.repository_path,
                stage_name="explore",
                session_id=session_id,
                resume_session=resume_session,
            )
            agent_execution._store_agent_output(context, result, "explore", raw_output)

        runtime._run_step_with_logging(context, self.name, self.skip, action)
