"""Tests for the ordered fallback agent provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from minions_army.infrastructure.agents.base import (
    AgentExecutionContext,
    AgentProvider,
)
from user_data.agent_providers.fallback import (
    DEFAULT_PROVIDER_CHAIN,
    FallbackAgentProvider,
)


class _FakeProvider(AgentProvider):
    def __init__(
        self,
        name: str,
        *,
        has_key: bool = True,
        result: str | None = None,
        fail: bool = False,
        env: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self._has_key = has_key
        self._result = result
        self._fail = fail
        self._env = env or {}
        self.ran = False

    def configured_api_key(self, settings) -> str | None:  # type: ignore[override]
        return "sk-fake" if self._has_key else None

    def environment(self, settings) -> dict[str, str]:  # type: ignore[override]
        return dict(self._env)

    def setup_tool_name(self) -> str:  # type: ignore[override]
        return self.name

    def run(self, context: AgentExecutionContext) -> str:  # type: ignore[override]
        self.ran = True
        if self._fail:
            raise SystemExit(1)
        assert self._result is not None
        return self._result


def _context() -> AgentExecutionContext:
    return AgentExecutionContext(
        prompt="do it",
        cwd=Path("."),
        stage_name="explore",
        run_subprocess=lambda *a, **k: None,
    )


def _fallback_with(delegates: list[AgentProvider]) -> FallbackAgentProvider:
    provider = FallbackAgentProvider()
    provider._delegates = delegates
    return provider


def test_default_chain_is_claude_codex_kimi() -> None:
    assert DEFAULT_PROVIDER_CHAIN == (
        "user_data.agent_providers.claude.ClaudeAgentProvider",
        "user_data.agent_providers.codex.CodexAgentProvider",
        "user_data.agent_providers.kimi.KimiAgentProvider",
    )


def test_first_provider_wins_and_shorts_circuit() -> None:
    first = _FakeProvider("claude", result="from-claude")
    second = _FakeProvider("codex", result="from-codex")
    provider = _fallback_with([first, second])

    assert provider.run(_context()) == "from-claude"
    assert first.ran is True
    assert second.ran is False


def test_falls_through_to_next_provider_on_failure() -> None:
    first = _FakeProvider("claude", fail=True)
    second = _FakeProvider("codex", result="from-codex")
    third = _FakeProvider("kimi", result="from-kimi")
    provider = _fallback_with([first, second, third])

    assert provider.run(_context()) == "from-codex"
    assert first.ran is True
    assert second.ran is True
    assert third.ran is False


def test_skips_providers_without_configured_key() -> None:
    first = _FakeProvider("claude", has_key=False, result="from-claude")
    second = _FakeProvider("codex", result="from-codex")
    provider = _fallback_with([first, second])

    assert provider.run(_context()) == "from-codex"
    assert first.ran is False
    assert second.ran is True


def test_raises_when_all_providers_fail() -> None:
    first = _FakeProvider("claude", fail=True)
    second = _FakeProvider("codex", fail=True)
    provider = _fallback_with([first, second])

    with pytest.raises(SystemExit):
        provider.run(_context())


def test_raises_when_no_provider_has_a_key() -> None:
    first = _FakeProvider("claude", has_key=False)
    second = _FakeProvider("codex", has_key=False)
    provider = _fallback_with([first, second])

    with pytest.raises(SystemExit):
        provider.run(_context())


def test_environment_merges_keys_from_providers_with_keys() -> None:
    first = _FakeProvider("claude", env={"ANTHROPIC_API_KEY": "a"})
    second = _FakeProvider("codex", env={"OPENAI_API_KEY": "o"})
    third = _FakeProvider("kimi", has_key=False, env={"KIMI_API_KEY": "k"})
    provider = _fallback_with([first, second, third])

    assert provider.environment(object()) == {
        "ANTHROPIC_API_KEY": "a",
        "OPENAI_API_KEY": "o",
    }


def test_setup_tool_name_uses_first_available_provider() -> None:
    first = _FakeProvider("claude", has_key=False)
    second = _FakeProvider("codex")
    provider = _fallback_with([first, second])

    assert provider.setup_tool_name() == "codex"


def test_does_not_share_session() -> None:
    assert FallbackAgentProvider().supports_shared_session() is False
