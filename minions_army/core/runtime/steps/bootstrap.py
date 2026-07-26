"""Pipeline step implementation."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from minions_army.application.services.orchestration_service import (
    PipelineContext,
)
from minions_army.core.runtime import orchestrator_runtime as runtime
from minions_army.core.runtime.logging import format_command, log_event

logger = logging.getLogger("minions_army.core.runtime.orchestrator_runtime")


@dataclass
class _BaseBootstrapStep:
    framework: str
    name: str = "bootstrap"
    skip: bool = False

    def build_command(self, provider_tool: str) -> list[str]:
        raise NotImplementedError

    def execute(self, context: PipelineContext) -> None:
        def action() -> None:
            result = context.require_result()
            agent_provider = runtime._agent_provider()
            provider_tool = agent_provider.setup_tool_name()
            command = self.build_command(provider_tool)
            log_event(
                logger,
                logging.INFO,
                "framework.bootstrap.prepared",
                framework=self.framework,
                agent_provider=agent_provider.name,
                agent_setup_tool=provider_tool,
                bootstrap_tool=command[0],
                command=format_command(command),
                repository_path=result.repository_path,
                **{
                    "agent.provider_class": runtime.settings.agent.provider_class,
                    "workflow.steps_provider_class": runtime.settings.workflow.steps_provider_class,
                },
            )
            runtime.run_command(command, result.repository_path)

        runtime._run_step_with_logging(context, self.name, self.skip, action)


@dataclass
class SpecKitBootstrapStep(_BaseBootstrapStep):
    framework: str = "speckit"

    def build_command(self, provider_tool: str) -> list[str]:
        return [
            "specify",
            "init",
            "--here",
            "--integration",
            provider_tool,
            "--integration-options",
            "--skills",
            "--force",
        ]


@dataclass
class OpenSpecBootstrapStep(_BaseBootstrapStep):
    framework: str = "openspec"

    def build_command(self, provider_tool: str) -> list[str]:
        return ["openspec", "init", "--tools", provider_tool, "--force"]
