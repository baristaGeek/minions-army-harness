"""Tests for the orchestrator entrypoint."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from minions_army.cli.commands import run as run_command
from minions_army.cli.commands.run import MinionOrchestrator, main


def test_build_request_requires_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    orchestrator = MinionOrchestrator()
    monkeypatch.delenv("MINION_INPUT_MESSAGE", raising=False)

    with pytest.raises(SystemExit, match="Missing required runtime configuration"):
        orchestrator._build_request()


def test_build_request_requires_anthropic_key_for_claude(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = MinionOrchestrator()
    monkeypatch.setenv("MINION_INPUT_MESSAGE", "hello")
    monkeypatch.setattr("minions_army.core.config.loader.config.repository.name", "owner/repo")
    monkeypatch.setattr(
        "minions_army.core.config.loader.config.agent.provider_class",
        "user_data.agent_providers.claude.ClaudeAgentProvider",
    )
    monkeypatch.setattr("minions_army.core.config.loader.config.agent.anthropic_api_key", None)

    with pytest.raises(SystemExit, match="agent.anthropic_api_key is required"):
        orchestrator._build_request()


def test_build_request_uses_defaults_and_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    orchestrator = MinionOrchestrator()
    monkeypatch.setenv("MINION_INPUT_MESSAGE", "hello")
    monkeypatch.setenv("MINION_CONTAINER_NAME", "container-x")
    monkeypatch.delenv("REPOSITORY_NAME", raising=False)
    monkeypatch.delenv("REPOSITORY_BASE_BRANCH", raising=False)
    monkeypatch.delenv("REPOSITORY_FEATURE_BRANCH", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr("minions_army.core.config.loader.config.repository.name", "owner/repo")
    monkeypatch.setattr(
        "minions_army.core.config.loader.config.agent.provider_class",
        "user_data.agent_providers.claude.ClaudeAgentProvider",
    )
    monkeypatch.setattr("minions_army.core.config.loader.config.repository.base_branch", "develop")
    monkeypatch.setattr(
        "minions_army.core.config.loader.config.repository.feature_branch", "feature/custom"
    )
    monkeypatch.setattr(
        "minions_army.core.config.loader.config.repository.github_token", "ghp_test"
    )
    monkeypatch.setattr(
        "minions_army.core.config.loader.config.agent.anthropic_api_key", "sk-ant-test"
    )
    monkeypatch.setattr(
        "minions_army.core.config.loader.config.workflow.steps_provider_class",
        "user_data.pipeline_steps.openspec.OpenSpecPipelineStepsProvider",
    )

    request = orchestrator._build_request()

    assert request.base_branch == "develop"
    assert request.feature_branch == "feature/custom"
    assert request.container_name == "container-x"
    assert request.spec_framework == "openspec"
    assert request.github_token == "ghp_test"


def test_build_request_logs_selected_agent_and_workflow(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    orchestrator = MinionOrchestrator()
    monkeypatch.setenv("MINION_INPUT_MESSAGE", "hello")
    monkeypatch.setattr("minions_army.core.config.loader.config.repository.name", "owner/repo")
    monkeypatch.setattr(
        "minions_army.core.config.loader.config.agent.provider_class",
        "user_data.agent_providers.codex.CodexAgentProvider",
    )
    monkeypatch.setitem(
        run_command.config.agent.model_extra,
        "openai_api_key",
        "sk-openai-test",
    )

    with caplog.at_level(logging.INFO, logger="minions_army.cli.commands.run"):
        orchestrator._build_request()

    assert "event=orchestrator.config.selected" in caplog.text
    assert "agent_provider=codex" in caplog.text
    assert "agent_setup_tool=codex" in caplog.text
    assert "agent_api_key_config_name=openai_api_key" in caplog.text
    assert "workflow_provider=openspec" in caplog.text
    assert "agent.provider_class=user_data.agent_providers.codex.CodexAgentProvider" in caplog.text
    assert (
        "workflow.steps_provider_class=user_data.pipeline_steps.openspec.OpenSpecPipelineStepsProvider"
        in caplog.text
    )


def test_main_raises_system_exit_with_run_result() -> None:
    with patch("minions_army.cli.commands.run.MinionOrchestrator.run", return_value=0):
        with pytest.raises(SystemExit, match="0"):
            main(argv=[])


def test_run_wires_service_and_returns_success(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    orchestrator = MinionOrchestrator()
    monkeypatch.setenv("MINION_INPUT_MESSAGE", "hello")
    monkeypatch.delenv("REPOSITORY_NAME", raising=False)
    monkeypatch.setattr("minions_army.core.config.loader.config.repository.name", "owner/repo")
    monkeypatch.setattr(
        "minions_army.core.config.loader.config.agent.provider_class",
        "user_data.agent_providers.claude.ClaudeAgentProvider",
    )
    monkeypatch.setattr(
        "minions_army.core.config.loader.config.agent.anthropic_api_key", "sk-ant-test"
    )

    class FakeService:
        def __init__(self) -> None:
            self.request = None

        def execute(self, request):
            self.request = request
            return object()

    fake_service = FakeService()

    with (
        caplog.at_level(logging.INFO, logger="minions_army.cli.commands.run"),
        patch(
            "minions_army.cli.commands.run.MinionOrchestrationService", return_value=fake_service
        ),
        patch("minions_army.cli.commands.run.SubprocessPipelineRunner"),
    ):
        assert orchestrator.run() == 0

    assert fake_service.request.repository_name == "owner/repo"
