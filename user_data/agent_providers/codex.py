"""Codex CLI agent provider."""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from pathlib import Path

from minions_army.core.config.loader import config as settings
from minions_army.core.runtime.logging import format_command, log_event
from minions_army.infrastructure.agents.base import AgentExecutionContext, AgentProvider

logger = logging.getLogger("minions_army.agent_providers.codex")
_CODEX_LOGIN_READY = False


class CodexAgentProvider(AgentProvider):
    name = "codex"
    model = "gpt-5.4-mini"
    reasoning_effort = "low"
    allowed_tools = "Bash,Read,Edit,Write,Glob,Grep"
    api_key_config_name = "openai_api_key"
    api_key_environment_variable = "OPENAI_API_KEY"
    dspy_provider_name = "openai"

    def setup_tool_name(self) -> str:
        return "codex"

    def _api_key_fingerprint(self) -> str | None:
        api_key = self.configured_api_key(settings)
        if not api_key:
            return None
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]

    def _ensure_logged_in(self, context: AgentExecutionContext) -> None:
        global _CODEX_LOGIN_READY
        if _CODEX_LOGIN_READY:
            return

        api_key = self.configured_api_key(settings)
        if not api_key:
            return

        context.run_subprocess(
            ["codex", "logout"],
            step=f"agent:{context.stage_name}:codex-logout",
            cwd=context.cwd,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, **self.environment(settings)},
        )
        log_event(
            logger,
            logging.INFO,
            "agent.codex.logout.completed",
            stage_name=context.stage_name,
            api_key_fingerprint=self._api_key_fingerprint(),
        )

        log_event(
            logger,
            logging.INFO,
            "agent.codex.login.start",
            stage_name=context.stage_name,
            api_key_fingerprint=self._api_key_fingerprint(),
        )
        login = context.run_subprocess(
            ["codex", "login", "--with-api-key"],
            step=f"agent:{context.stage_name}:codex-login",
            cwd=context.cwd,
            check=False,
            capture_output=True,
            text=True,
            input=f"{api_key}\n",
            env={**os.environ, **self.environment(settings)},
        )
        if login.returncode != 0:
            log_event(
                logger,
                logging.ERROR,
                "agent.codex.login.failed",
                stage_name=context.stage_name,
                exit_code=login.returncode,
                stdout_tail=(login.stdout or "")[-1200:],
                stderr_tail=(login.stderr or "")[-1200:],
            )
            raise SystemExit(login.returncode)

        _CODEX_LOGIN_READY = True
        log_event(
            logger,
            logging.INFO,
            "agent.codex.login.completed",
            stage_name=context.stage_name,
            api_key_fingerprint=self._api_key_fingerprint(),
        )

    def run(self, context: AgentExecutionContext) -> str:
        self._ensure_logged_in(context)
        response_file = Path(tempfile.gettempdir()) / "codex-response.txt"
        command = [
            "codex",
            "exec",
            "--output-last-message",
            str(response_file),
            "--config",
            f'model="{self.model}"',
            "--config",
            f'model_reasoning_effort="{self.reasoning_effort}"',
            "--sandbox",
            "danger-full-access",
            context.prompt,
        ]
        log_event(
            logger,
            logging.INFO,
            "agent.stage.command.start",
            stage_name=context.stage_name,
            engine=self.name,
            command=format_command(command),
            cwd=context.cwd,
            model=self.model,
            reasoning_effort=self.reasoning_effort,
            api_key_config_name=self.api_key_config_name,
            api_key_environment_variable=self.api_key_environment_variable,
            has_configured_api_key=bool(self.configured_api_key(settings)),
            api_key_fingerprint=self._api_key_fingerprint(),
        )
        completed = context.run_subprocess(
            command,
            step=f"agent:{context.stage_name}",
            cwd=context.cwd,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, **self.environment(settings)},
        )
        if completed.returncode != 0:
            log_event(
                logger,
                logging.ERROR,
                "agent.stage.command.failed",
                stage_name=context.stage_name,
                engine=self.name,
                command=command,
                cwd=context.cwd,
                exit_code=completed.returncode,
                stdout_tail=(completed.stdout or "")[-1200:],
                stderr_tail=(completed.stderr or "")[-1200:],
            )
            raise SystemExit(completed.returncode)
        log_event(
            logger,
            logging.INFO,
            "agent.stage.command.succeeded",
            stage_name=context.stage_name,
            engine=self.name,
            exit_code=completed.returncode,
        )
        return response_file.read_text(encoding="utf-8")
