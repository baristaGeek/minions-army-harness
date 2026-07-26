"""Fallback agent provider.

Runs an ordered chain of agent providers and falls through to the next one
whenever a provider fails (out of credits, rate limited, CLI/login error, ...).

Default order: Claude -> Codex -> Kimi. Override with an optional
``agent.fallback_provider_classes`` list in config.

Providers today signal every failure by raising ``SystemExit`` from ``run()``
(see claude/codex/kimi providers). We treat any ``SystemExit`` (or unexpected
exception) from a delegate as "this provider is unavailable" and advance to the
next one. Only when the whole chain is exhausted do we raise, so a single
provider running out of credits no longer aborts the pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

from minions_army.core.config.loader import config as settings
from minions_army.core.runtime.logging import log_event
from minions_army.infrastructure.agents.base import AgentExecutionContext, AgentProvider
from minions_army.infrastructure.agents.loader import load_agent_provider

logger = logging.getLogger("minions_army.agent_providers.fallback")

DEFAULT_PROVIDER_CHAIN = (
    "user_data.agent_providers.claude.ClaudeAgentProvider",
    "user_data.agent_providers.codex.CodexAgentProvider",
    "user_data.agent_providers.kimi.KimiAgentProvider",
)


class FallbackAgentProvider(AgentProvider):
    """Try each configured provider in priority order until one succeeds."""

    name = "fallback"
    model = "fallback"
    reasoning_effort = "low"
    allowed_tools = "Bash,Read,Edit,Write,Glob,Grep"

    def __init__(self) -> None:
        self._delegates: list[AgentProvider] | None = None

    # -- chain construction -------------------------------------------------

    def _provider_class_chain(self, settings: Any) -> list[str]:
        configured = getattr(settings.agent, "fallback_provider_classes", None)
        if configured:
            return [str(entry) for entry in configured]
        return list(DEFAULT_PROVIDER_CHAIN)

    def delegates(self, settings: Any) -> list[AgentProvider]:
        if self._delegates is None:
            self._delegates = [
                load_agent_provider(class_path)
                for class_path in self._provider_class_chain(settings)
            ]
        return self._delegates

    def _available_delegates(self, settings: Any) -> list[AgentProvider]:
        return [
            provider
            for provider in self.delegates(settings)
            if provider.configured_api_key(settings)
        ]

    # -- AgentProvider contract --------------------------------------------

    def supports_shared_session(self) -> bool:
        # A session id minted for one provider is meaningless to the next, and a
        # stage may fall over to a different provider than the previous stage.
        # Keep every stage independent so the chain stays robust.
        return False

    def setup_tool_name(self) -> str:
        for provider in self.delegates(settings):
            if provider.configured_api_key(settings):
                return provider.setup_tool_name()
        return self.delegates(settings)[0].setup_tool_name()

    def environment(self, settings: Any) -> dict[str, str]:
        environment: dict[str, str] = {}
        for provider in self.delegates(settings):
            if not provider.configured_api_key(settings):
                continue
            try:
                environment.update(provider.environment(settings))
            except SystemExit:
                # A delegate's environment() may raise (e.g. Kimi materialising
                # its config). Skip it rather than break env assembly.
                continue
        return environment

    def validate_config(self, settings: Any) -> None:
        available = [p.name for p in self._available_delegates(settings)]
        if not available:
            raise SystemExit(
                "FallbackAgentProvider requires at least one configured provider "
                "API key (agent.anthropic_api_key / openai_api_key / kimi_api_key)."
            )

    def run(self, context: AgentExecutionContext) -> str:
        delegates = self.delegates(settings)
        failures: list[str] = []
        attempted = 0
        for position, provider in enumerate(delegates, start=1):
            if not provider.configured_api_key(settings):
                log_event(
                    logger,
                    logging.INFO,
                    "agent.fallback.skipped",
                    stage_name=context.stage_name,
                    provider=provider.name,
                    position=position,
                    reason="missing_api_key",
                )
                continue
            attempted += 1
            log_event(
                logger,
                logging.INFO,
                "agent.fallback.attempt",
                stage_name=context.stage_name,
                provider=provider.name,
                position=position,
                total=len(delegates),
            )
            try:
                result = provider.run(context)
            except SystemExit as exc:
                failures.append(f"{provider.name}: exit={exc.code}")
                log_event(
                    logger,
                    logging.WARNING,
                    "agent.fallback.provider_failed",
                    stage_name=context.stage_name,
                    provider=provider.name,
                    position=position,
                    error=str(exc.code),
                )
                continue
            except Exception as exc:  # noqa: BLE001 - never let one provider abort the chain
                failures.append(f"{provider.name}: {exc!r}")
                log_event(
                    logger,
                    logging.WARNING,
                    "agent.fallback.provider_failed",
                    stage_name=context.stage_name,
                    provider=provider.name,
                    position=position,
                    error=repr(exc),
                )
                continue
            log_event(
                logger,
                logging.INFO,
                "agent.fallback.succeeded",
                stage_name=context.stage_name,
                provider=provider.name,
                position=position,
            )
            return result

        log_event(
            logger,
            logging.ERROR,
            "agent.fallback.exhausted",
            stage_name=context.stage_name,
            attempted=attempted,
            failures="; ".join(failures) or "no_providers_with_api_key",
        )
        raise SystemExit(
            f"All fallback providers failed for stage '{context.stage_name}'. "
            f"Attempts: {'; '.join(failures) or 'none (no configured API keys)'}"
        )
