"""Minion workflow orchestrator entrypoint."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import minions_army.infrastructure.observability.logging_config as _logging_config  # noqa: F401
from minions_army.application.services.orchestration_service import (
    MinionOrchestrationService,
    OrchestrationRequest,
)
from minions_army.core.config.loader import config, reload_config
from minions_army.core.runtime.logging import log_event
from minions_army.core.runtime.orchestrator_runtime import SubprocessPipelineRunner
from minions_army.infrastructure.agents.loader import load_agent_provider
from minions_army.infrastructure.pipeline_steps.loader import load_pipeline_steps_provider

logger = logging.getLogger(__name__)


class MinionOrchestrator:
    """Thin launcher that builds the application service and runs it."""

    def __init__(self) -> None:
        pass

    def run(self) -> int:
        """Run the pipeline from specification through implementation."""
        log_event(logger, logging.INFO, "orchestrator.run.started")
        request = self._build_request()
        log_event(
            logger,
            logging.INFO,
            "orchestrator.request.built",
            spec_framework=request.spec_framework,
            execution_backend=config.launcher.backend,
            repository=request.repository_name,
        )
        service = MinionOrchestrationService(
            pipeline_runner=SubprocessPipelineRunner(),
        )
        service.execute(request)
        log_event(logger, logging.INFO, "orchestrator.run.completed")
        return 0

    def _build_request(self) -> OrchestrationRequest:
        required = ["MINION_INPUT_MESSAGE"]
        missing = [name for name in required if not os.environ.get(name)]
        repository_name = os.environ.get("REPOSITORY_NAME") or config.repository.name or ""
        if not repository_name:
            missing.append("REPOSITORY_NAME")
        if missing:
            raise SystemExit(f"Missing required runtime configuration: {', '.join(missing)}")

        agent_provider = load_agent_provider(config.agent.provider_class)
        agent_provider.validate_config(config)
        steps_provider = load_pipeline_steps_provider(config.workflow.steps_provider_class)
        log_event(
            logger,
            logging.INFO,
            "orchestrator.config.selected",
            agent_provider=agent_provider.name,
            agent_setup_tool=agent_provider.setup_tool_name(),
            agent_api_key_config_name=agent_provider.api_key_config_name,
            workflow_provider=steps_provider.name,
            **{
                "agent.provider_class": config.agent.provider_class,
                "workflow.steps_provider_class": config.workflow.steps_provider_class,
            },
        )

        return OrchestrationRequest(
            repository_name=repository_name,
            minion_input_message=os.environ["MINION_INPUT_MESSAGE"],
            base_branch=os.environ.get("REPOSITORY_BASE_BRANCH", config.repository.base_branch),
            feature_branch=os.environ.get(
                "REPOSITORY_FEATURE_BRANCH", config.repository.feature_branch
            ),
            container_name=os.environ.get(
                "MINION_CONTAINER_NAME", os.environ.get("HOSTNAME", "minion")
            ),
            spec_framework=steps_provider.name,
            github_token=os.environ.get("GITHUB_TOKEN", config.repository.github_token),
        )


def main(argv: list[str] | None = None) -> None:
    """Run the orchestrator once and exit."""
    parser = argparse.ArgumentParser(prog="minion-orchestrator")
    parser.add_argument("--config", default=None, help="Path to config file")
    args = parser.parse_args(argv)

    if args.config:
        reload_config(Path(args.config))

    orchestrator = MinionOrchestrator()
    raise SystemExit(orchestrator.run())
