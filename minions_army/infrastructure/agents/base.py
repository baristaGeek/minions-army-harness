"""Base contract for user-defined agent providers."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RunSubprocess = Callable[..., subprocess.CompletedProcess]


@dataclass(frozen=True)
class AgentExecutionContext:
    """Runtime-only context passed to an agent provider."""

    prompt: str
    cwd: Path
    stage_name: str
    run_subprocess: RunSubprocess
    session_id: str | None = None
    resume_session: bool = False


class AgentProvider:
    """Strategy base class for executing one agent stage."""

    name: str
    model: str
    reasoning_effort: str
    allowed_tools: str
    api_key_config_name: str | None = None
    api_key_environment_variable: str | None = None
    dspy_provider_name: str | None = None

    def run(self, context: AgentExecutionContext) -> str:
        raise NotImplementedError

    def setup_tool_name(self) -> str:
        """Tool name used by framework bootstrappers such as `openspec init`."""
        return self.name

    def supports_shared_session(self) -> bool:
        return False

    def environment(self, settings: Any) -> dict[str, str]:
        """Environment variables required by this provider."""
        api_key = self.configured_api_key(settings)
        if not api_key or not self.api_key_environment_variable:
            return {}
        return {self.api_key_environment_variable: api_key}

    def validate_config(self, settings: Any) -> None:
        """Optional provider-specific runtime validation."""
        if not self.api_key_config_name:
            raise SystemExit(
                f"{self.__class__.__module__}.{self.__class__.__name__} must define "
                "api_key_config_name"
            )
        if not self.configured_api_key(settings):
            raise SystemExit(
                f"agent.{self.api_key_config_name} is required when "
                f"agent.provider_class={self.__class__.__module__}.{self.__class__.__name__}"
            )

    def configured_api_key(self, settings: Any) -> str | None:
        """Read this provider's configured API key from agent config."""
        if not self.api_key_config_name:
            return None
        value = getattr(settings.agent, self.api_key_config_name, None)
        if value:
            return str(value)
        return None

    def dspy_model_name(self, model: str) -> str:
        """Return the DSPy/LiteLLM model name for this provider."""
        if "/" in model:
            return model
        provider_name = self.dspy_provider_name or self.name
        return f"{provider_name}/{model}"
