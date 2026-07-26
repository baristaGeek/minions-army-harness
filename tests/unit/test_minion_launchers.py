"""Tests for minion execution launchers."""

import re
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from minions_army.domain.models import SlackMessage, WebAPIMessage
from minions_army.infrastructure.launchers import factory as minion_launchers
from minions_army.infrastructure.launchers.factory import (
    CloudJobsRunTaskRunner,
    DockerSiblingTaskRunner,
    FlyMachinesTaskRunner,
    build_minion_task_runner,
)


@pytest.fixture(autouse=True)
def _no_slack(monkeypatch) -> None:
    """Keep launcher tests hermetic: never post to Slack over the network."""
    monkeypatch.setattr(minion_launchers, "post_slack_message", lambda *a, **k: None)
    monkeypatch.setattr(
        minion_launchers.settings.agent,
        "provider_class",
        "user_data.agent_providers.codex.CodexAgentProvider",
    )
    monkeypatch.setitem(
        minion_launchers.settings.agent.model_extra,
        "openai_api_key",
        "sk-openai-test",
    )


def test_run_for_message_passes_repo_environment(monkeypatch) -> None:
    """The minion container receives repository settings and a random name."""

    recorded_kwargs: dict[str, Any] = {}

    class FakeContainers:
        def run(self, **kwargs: Any) -> SimpleNamespace:
            recorded_kwargs.update(kwargs)
            return SimpleNamespace(id="container-123")

    fake_docker = SimpleNamespace(from_env=lambda: SimpleNamespace(containers=FakeContainers()))

    monkeypatch.setitem(sys.modules, "docker", fake_docker)
    monkeypatch.setattr(minion_launchers.settings.repository, "github_token", "ghp_test")
    monkeypatch.setattr(minion_launchers.settings.repository, "name", "minions-army")
    monkeypatch.setattr(minion_launchers.settings.repository, "base_branch", "main")
    monkeypatch.setattr(
        minion_launchers.settings.database,
        "url",
        "postgresql+asyncpg://user:pass@db:5432/minions_army",
    )
    monkeypatch.setattr(
        minion_launchers.settings.repository,
        "feature_branch",
        "feature/test-minion",
    )
    monkeypatch.setattr(
        minion_launchers.settings.launcher,
        "codex_home",
        r"C:\Users\TestUser\.codex",
    )

    runner = DockerSiblingTaskRunner(image="minion-image")
    message = SlackMessage(id=7, channel_id="C123", text="clone repo")

    runner.run_for_message(message)

    assert recorded_kwargs["image"] == "minion-image"
    assert recorded_kwargs["command"] == ["minion-orchestrator"]
    assert re.fullmatch(r"minion_[0-9a-f]{12}", recorded_kwargs["name"])
    container_name = recorded_kwargs["name"]
    environment = recorded_kwargs["environment"]
    assert environment["MINION_INPUT_MESSAGE"] == "clone repo"
    assert environment["DATABASE_URL"] == "postgresql+asyncpg://user:pass@db:5432/minions_army"
    assert environment["GITHUB_TOKEN"] == "ghp_test"
    assert environment["MINION_CONTAINER_NAME"] == container_name
    assert environment["CODEX_HOME"] == "/root/.codex"
    assert environment["REPOSITORY_NAME"] == "minions-army"
    assert environment["REPOSITORY_BASE_BRANCH"] == "main"
    assert environment["REPOSITORY_FEATURE_BRANCH"] == "feature/test-minion"
    assert "MINION_MODEL" not in environment
    assert "MINION_AGENT_ENGINE" not in environment
    assert "MINION_DEPLOY_MODE" not in environment
    assert recorded_kwargs["volumes"] == {
        r"C:\Users\TestUser\.codex": {
            "bind": "/root/.codex",
            "mode": "rw",
        }
    }


def test_base_environment_accepts_slack_token(monkeypatch) -> None:
    monkeypatch.setattr(minion_launchers.settings.slack, "bot_token", None)
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-token")

    runner = DockerSiblingTaskRunner(image="minion-image")
    environment = runner._base_environment(SlackMessage(id=7, channel_id="C123", text="clone repo"))

    assert environment["SLACK_BOT_TOKEN"] == "xoxb-token"


def test_base_environment_uses_provider_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        minion_launchers.settings.agent,
        "provider_class",
        "user_data.agent_providers.kimi.KimiAgentProvider",
    )
    monkeypatch.setenv("KIMI_API_KEY", "sk-kimi-test")
    monkeypatch.setitem(minion_launchers.settings.agent.model_extra, "kimi_api_key", None)
    (tmp_path / "config.toml").write_text(
        'api_key = "${KIMI_API_KEY}"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "user_data.agent_providers.kimi.KimiAgentProvider._runtime_home",
        lambda self: tmp_path,
    )
    monkeypatch.setattr(
        "user_data.agent_providers.kimi.KimiAgentProvider._config_template_path",
        lambda self: tmp_path / "config.toml",
    )
    runner = DockerSiblingTaskRunner(image="minion-image")
    environment = runner._base_environment(SlackMessage(id=7, channel_id="C123", text="clone repo"))

    assert "KIMI_CODE_HOME" not in environment
    assert environment["KIMI_API_KEY"] == "sk-kimi-test"
    assert environment["MOONSHOT_API_KEY"] == "sk-kimi-test"
    assert 'api_key = "sk-kimi-test"' in (tmp_path / "config.toml").read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY" not in environment


def test_base_environment_uses_codex_api_key_for_codex_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        minion_launchers.settings.agent,
        "provider_class",
        "user_data.agent_providers.codex.CodexAgentProvider",
    )
    monkeypatch.setitem(
        minion_launchers.settings.agent.model_extra, "openai_api_key", "sk-openai-test"
    )

    runner = DockerSiblingTaskRunner(image="minion-image")
    environment = runner._base_environment(SlackMessage(id=7, channel_id="C123", text="clone repo"))

    assert environment["OPENAI_API_KEY"] == "sk-openai-test"
    assert "ANTHROPIC_API_KEY" not in environment
    assert "KIMI_MODEL_API_KEY" not in environment


def test_base_environment_accepts_webapi_context() -> None:
    runner = DockerSiblingTaskRunner(image="minion-image")
    environment = runner._base_environment(
        WebAPIMessage(
            id=9,
            session_id="session-123",
            text="clone repo",
            user_id="user-123",
        )
    )

    assert environment["MINION_INPUT_MESSAGE"] == "clone repo"
    assert environment["MINION_WEBHOOK_SOURCE"] == "webapi"
    assert environment["WEBAPI_SESSION_ID"] == "session-123"
    assert environment["WEBAPI_MESSAGE_ID"] == "9"
    assert environment["WEBAPI_USER_ID"] == "user-123"
    assert "SLACK_CHANNEL_ID" not in environment


def test_message_environment_rejects_unknown_message_type() -> None:
    runner = DockerSiblingTaskRunner(image="minion-image")

    with pytest.raises(TypeError, match="Unsupported webhook message type"):
        runner._message_environment(object())  # type: ignore[arg-type]


def test_run_for_message_returns_when_docker_sdk_is_missing(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "docker", None)
    runner = DockerSiblingTaskRunner(image="minion-image")
    message = SlackMessage(id=7, channel_id="C123", text="clone repo")

    runner.run_for_message(message)


def test_run_for_message_logs_when_container_start_fails(monkeypatch) -> None:
    class FakeContainers:
        def run(self, **kwargs: Any) -> SimpleNamespace:
            raise RuntimeError("boom")

    fake_docker = SimpleNamespace(from_env=lambda: SimpleNamespace(containers=FakeContainers()))
    monkeypatch.setitem(sys.modules, "docker", fake_docker)

    runner = DockerSiblingTaskRunner(image="minion-image")
    message = SlackMessage(id=7, channel_id="C123", text="clone repo")

    runner.run_for_message(message)


def test_build_minion_task_runner_selects_docker(monkeypatch) -> None:
    monkeypatch.setattr(minion_launchers.settings.launcher, "backend", "docker")

    runner = build_minion_task_runner()

    assert isinstance(runner, DockerSiblingTaskRunner)


def test_build_minion_task_runner_selects_cloud_jobs(monkeypatch) -> None:
    monkeypatch.setattr(minion_launchers.settings.launcher, "backend", "cloud_jobs")

    runner = build_minion_task_runner()

    assert isinstance(runner, CloudJobsRunTaskRunner)


def test_cloud_jobs_run_task_runner_builds_submission_command(monkeypatch) -> None:
    recorded: list[list[str]] = []

    def fake_run(command, check, capture_output, text):
        recorded.append(command)
        if command[:4] == ["gcloud", "run", "jobs", "describe"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="not found")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("minions_army.infrastructure.launchers.factory.subprocess.run", fake_run)
    monkeypatch.setattr(
        "minions_army.infrastructure.launchers.factory.shutil.which", lambda name: "/usr/bin/gcloud"
    )
    monkeypatch.setattr(minion_launchers.settings.repository, "name", "owner/repo")
    monkeypatch.setattr(minion_launchers.settings.repository, "github_token", "token")
    monkeypatch.setattr(minion_launchers.settings.launcher, "codex_home", None)
    monkeypatch.setattr(minion_launchers.settings.launcher, "cloud_run_project", "test-project")
    monkeypatch.setattr(minion_launchers.settings.launcher, "cloud_run_region", "us-central1")
    monkeypatch.setattr(minion_launchers.settings.launcher, "cloud_run_job_name", "test-job")

    runner = CloudJobsRunTaskRunner(image="minion-image")
    message = SlackMessage(id=7, channel_id="C123", text="clone repo")

    runner.run_for_message(message)

    assert recorded[0][0:4] == ["gcloud", "run", "jobs", "describe"]
    assert recorded[1][0:4] == ["gcloud", "run", "jobs", "create"]
    assert recorded[1][4] == "test-job"
    assert "--env-vars-file=" in " ".join(recorded[1])
    assert "--execute-now" in recorded[1]
    assert "--wait" in recorded[1]


def test_build_minion_task_runner_selects_fly_machines(monkeypatch) -> None:
    monkeypatch.setattr(minion_launchers.settings.launcher, "backend", "fly_machines")

    runner = build_minion_task_runner()

    assert isinstance(runner, FlyMachinesTaskRunner)


def test_build_minion_task_runner_rejects_unknown_backend(monkeypatch) -> None:
    monkeypatch.setattr(minion_launchers.settings.launcher, "backend", "bogus")

    with pytest.raises(SystemExit, match="Unsupported MINION_EXECUTION_BACKEND"):
        build_minion_task_runner()


def test_fly_machines_runner_builds_machine_run_command(monkeypatch) -> None:
    recorded: list[list[str]] = []

    def fake_run(command, check, capture_output, text, env):
        recorded.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("minions_army.infrastructure.launchers.factory.subprocess.run", fake_run)
    monkeypatch.setattr(
        "minions_army.infrastructure.launchers.factory.shutil.which", lambda name: "/usr/bin/flyctl"
    )
    monkeypatch.setattr(minion_launchers.settings.repository, "name", "owner/repo")
    monkeypatch.setattr(
        minion_launchers.settings.launcher, "fly_machine_app", "minions-army-minion"
    )
    monkeypatch.setattr(minion_launchers.settings.launcher, "fly_app", "your-fly-app")
    monkeypatch.setattr(minion_launchers.settings.launcher, "fly_api_token", "fly-token")
    monkeypatch.setattr(minion_launchers.settings.launcher, "fly_region", "fra")
    monkeypatch.setattr(
        minion_launchers.settings.database,
        "url",
        "postgresql+asyncpg://user:pass@db:5432/minions_army",
    )

    runner = FlyMachinesTaskRunner(image="registry.fly.io/minion:latest")
    message = SlackMessage(id=7, channel_id="C123", text="clone repo")

    runner.run_for_message(message)

    assert recorded[0][0:3] == ["flyctl", "machine", "run"]
    assert recorded[0][3] == "registry.fly.io/minion:latest"
    # Launches in the minion host app, NOT the deploy-target app.
    assert recorded[0][recorded[0].index("--app") + 1] == "minions-army-minion"
    assert "--rm" in recorded[0]
    assert recorded[0][recorded[0].index("--vm-memory") + 1] == "2048"
    assert recorded[0][recorded[0].index("--command") + 1] == "minion-orchestrator"
    joined = " ".join(recorded[0])
    assert "MINION_INPUT_MESSAGE=clone repo" in joined
    assert "DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/minions_army" in joined


def test_fly_machines_runner_requires_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        "minions_army.infrastructure.launchers.factory.shutil.which", lambda name: "/usr/bin/flyctl"
    )
    monkeypatch.setattr(minion_launchers.settings.launcher, "fly_machine_app", None)
    monkeypatch.setattr(minion_launchers.settings.launcher, "fly_api_token", None)
    ran: list[str] = []
    monkeypatch.setattr(
        "minions_army.infrastructure.launchers.factory.subprocess.run",
        lambda *a, **k: ran.append("ran"),
    )

    runner = FlyMachinesTaskRunner(image="minion:latest")
    # Misconfiguration fails loud (consistent with the Cloud Run backend).
    with pytest.raises(SystemExit, match="Missing required Fly settings"):
        runner.run_for_message(SlackMessage(id=1, channel_id="C1", text="hi"))

    assert ran == []
