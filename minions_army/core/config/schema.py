"""YAML configuration schema for the runtime surface."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from minions_army.core.config.urls import normalize_database_url

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _resolve_env_placeholders(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_env_placeholders(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_env_placeholders(item) for item in value]
    if not isinstance(value, str):
        return value

    def replace(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1), "")

    return _ENV_PATTERN.sub(replace, value)


class AppConfig(BaseModel):
    """Application identity and runtime environment."""

    name: str = "minions-army"
    environment: str = "development"
    debug: bool = False


class DatabaseConfig(BaseModel):
    """Persistence configuration."""

    url: str = "postgresql+asyncpg://user:password@localhost:5432/minions_army"
    sync_url: str | None = None

    @field_validator("url")
    @classmethod
    def url_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "database.url is required; set DATABASE_URL or configure user_data/api/config.yml"
            )
        return value

    @property
    def async_url(self) -> str:
        return normalize_database_url(self.url, is_async=True)

    @property
    def migration_url(self) -> str:
        return normalize_database_url(self.sync_url or self.url, is_async=False)


class SlackConfig(BaseModel):
    """Slack inbound/outbound settings."""

    allowed_channel_id: str | None = None
    bot_token: str | None = None

    @field_validator("bot_token")
    @classmethod
    def bot_token_falls_back_to_env(cls, value: str | None) -> str | None:
        return value or os.environ.get("SLACK_BOT_TOKEN")


class RepositoryConfig(BaseModel):
    """Target repository settings for a minion run."""

    name: str | None = None
    base_branch: str = "main"
    feature_branch: str = "feature/minion-task"
    github_token: str | None = None


class AgentConfig(BaseModel):
    """Default agent execution settings."""

    model_config = ConfigDict(extra="allow")

    provider_class: str = "user_data.agent_providers.claude.ClaudeAgentProvider"


class WorkflowConfig(BaseModel):
    """Spec-driven-development workflow settings."""

    steps_provider_class: str = "user_data.pipeline_steps.openspec.OpenSpecPipelineStepsProvider"
    constitution_depth: str = "standard"


class LauncherConfig(BaseModel):
    """Minion workload launcher settings."""

    backend: str = "docker"
    image: str = "minions-army-minion:latest"
    codex_home: str | None = None
    cloud_run_project: str | None = None
    cloud_run_region: str | None = None
    cloud_run_job_name: str = "minions-army-minion"
    fly_machine_app: str | None = None
    fly_app: str | None = None
    fly_region: str = "fra"
    fly_api_token: str | None = None
    fly_vm_memory: int = 2048
    fly_vm_cpus: int = 2


class VerificationConfig(BaseModel):
    """Build/render verification gate."""

    command: str | None = None
    cwd: str = "."


class ReviewerConfig(BaseModel):
    """Automated reviewer settings."""

    enabled: bool = False
    model: str = "claude-haiku-4-5"
    engine: str = "claude_cli"
    compiled_path: str | None = None


class DeployConfig(BaseModel):
    """Post-review deployment settings."""

    mode: str = "none"


class MinionsConfig(BaseModel):
    """Root runtime configuration."""

    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    repository: RepositoryConfig = Field(default_factory=RepositoryConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    launcher: LauncherConfig = Field(default_factory=LauncherConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    reviewer: ReviewerConfig = Field(default_factory=ReviewerConfig)
    deploy: DeployConfig = Field(default_factory=DeployConfig)
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @classmethod
    def from_file(cls, path: Path) -> MinionsConfig:
        """Load a YAML config file."""
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("PyYAML is required to load YAML config files") from exc

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Config file must contain a YAML mapping: {path}")
        data = _resolve_env_placeholders(data)
        config = cls.model_validate(data)
        config.raw.update(data)
        return config
