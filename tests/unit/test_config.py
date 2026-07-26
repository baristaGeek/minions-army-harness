"""Tests for runtime configuration."""

from minions_army.core.config.loader import load_config
from minions_army.core.config.schema import MinionsConfig
from minions_army.core.config.urls import normalize_database_url


def test_load_config_reads_yaml_and_resolves_secret_placeholders(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    config = load_config("tests/fixtures/configs/runtime.yml")

    assert config.app.name == "test-app"
    assert config.app.environment == "production"
    assert config.app.debug is True
    assert config.database.url == "sqlite+aiosqlite:///./runtime.db"
    assert config.database.migration_url == "sqlite:///./runtime.db"
    assert config.repository.name == "owner/repo"
    assert config.repository.github_token == "ghp_test"
    assert config.agent.anthropic_api_key == "sk-ant-test"
    assert config.workflow.constitution_depth == "professional"
    assert config.launcher.backend == "fly_machines"


def test_slack_bot_token_supports_env_name(monkeypatch) -> None:
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-token")

    config = load_config("user_data/config.example.yml")

    assert config.slack.bot_token == "xoxb-token"


def test_load_config_returns_schema_defaults_when_file_is_missing() -> None:
    config = load_config("tests/fixtures/configs/missing.yml")

    assert isinstance(config, MinionsConfig)
    assert config.agent.provider_class == "user_data.agent_providers.claude.ClaudeAgentProvider"
    assert (
        config.workflow.steps_provider_class
        == "user_data.pipeline_steps.openspec.OpenSpecPipelineStepsProvider"
    )
    assert config.reviewer.enabled is False
    assert config.deploy.mode == "none"
    assert config.verification.cwd == "."


def test_agent_config_accepts_provider_specific_keys() -> None:
    config = MinionsConfig.model_validate(
        {"agent": {"openai_api_key": "sk-openai-test", "copilot_api_key": "copilot-test"}}
    )

    assert config.agent.openai_api_key == "sk-openai-test"
    assert config.agent.copilot_api_key == "copilot-test"


def test_normalize_database_url_handles_fly_postgres_format() -> None:
    fly = "postgres://u:p@minions-army-db.flycast:5432/db?sslmode=disable"
    assert (
        normalize_database_url(fly, is_async=True)
        == "postgresql+asyncpg://u:p@minions-army-db.flycast:5432/db?ssl=disable"
    )
    assert (
        normalize_database_url(fly, is_async=False)
        == "postgresql://u:p@minions-army-db.flycast:5432/db?sslmode=disable"
    )


def test_normalize_database_url_passthrough_for_asyncpg() -> None:
    url = "postgresql+asyncpg://user:pass@localhost:5432/minions_army"
    assert normalize_database_url(url, is_async=True) == url
    assert (
        normalize_database_url(url, is_async=False)
        == "postgresql://user:pass@localhost:5432/minions_army"
    )


def test_normalize_database_url_supports_non_postgres_urls() -> None:
    sqlite_url = "sqlite+aiosqlite:///./minions_army.db"
    assert normalize_database_url(sqlite_url, is_async=True) == sqlite_url
    assert normalize_database_url(sqlite_url, is_async=False) == "sqlite:///./minions_army.db"
