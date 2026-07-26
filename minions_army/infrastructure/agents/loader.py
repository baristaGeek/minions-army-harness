"""Load agent provider strategies by class path."""

from __future__ import annotations

import importlib

from minions_army.infrastructure.agents.base import AgentProvider


def load_agent_provider(class_path: str) -> AgentProvider:
    class_path = class_path.strip()
    if not class_path:
        raise SystemExit("agent.provider_class is required")
    module_name, separator, class_name = class_path.rpartition(".")
    if not separator or not module_name or not class_name:
        raise SystemExit(
            "agent.provider_class must be a Python class path like "
            "user_data.agent_providers.claude.ClaudeAgentProvider"
        )

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise SystemExit(
                f"Cannot import agent.provider_class '{class_path}'. "
                f"Create {module_name.replace('.', '/')}.py."
            ) from exc
        raise

    provider_class = getattr(module, class_name, None)
    if provider_class is None:
        raise SystemExit(f"{module_name} must define {class_name}")

    provider = provider_class()
    if not isinstance(provider, AgentProvider):
        raise SystemExit(f"{class_path} must extend AgentProvider")
    return provider
