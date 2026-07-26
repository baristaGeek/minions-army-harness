"""Kimi Code CLI agent provider."""

from __future__ import annotations

import logging
import os
import hashlib
import shutil
from pathlib import Path

from minions_army.core.config.loader import config as settings
from minions_army.core.runtime.logging import format_command, log_event
from minions_army.infrastructure.agents.base import AgentExecutionContext, AgentProvider

logger = logging.getLogger("minions_army.agent_providers.kimi")


class KimiAgentProvider(AgentProvider):
    name = "kimi"
    model = "kimi-k2.7-code"
    reasoning_effort = "low"
    allowed_tools = "Bash,Read,Edit,Write,Glob,Grep"
    api_key_config_name = "kimi_api_key"
    api_key_environment_variable = "KIMI_API_KEY"

    def supports_shared_session(self) -> bool:
        return True

    def _model_alias(self) -> str:
        return self.model

    def _runtime_home(self) -> Path:
        return Path.home() / ".kimi-code"

    def _runtime_config_path(self) -> Path:
        return self._runtime_home() / "config.toml"

    def _config_template_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "kimi_code_home" / "config.toml"

    def _toml_string(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _configured_api_key(self, settings) -> str | None:
        api_key = self.configured_api_key(settings)
        if api_key and api_key.startswith("${") and api_key.endswith("}"):
            api_key = os.environ.get(api_key[2:-1])
        return api_key or os.environ.get("KIMI_API_KEY")

    def _api_key_fingerprint(self, api_key: str | None) -> str | None:
        if not api_key:
            return None
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]

    def _write_config_api_key(self, settings) -> None:
        api_key = self._configured_api_key(settings)
        if not api_key:
            raise SystemExit(
                "Kimi API key is missing. Set agent.kimi_api_key to a real key or set KIMI_API_KEY."
        )

        config_path = self._runtime_config_path()
        template_path = self._config_template_path()
        if not template_path.is_file():
            raise SystemExit(f"Kimi config template not found: {template_path}")

        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_text = template_path.read_text(encoding="utf-8")
        lines = config_text.splitlines()
        escaped_api_key = self._toml_string(api_key)
        for index, line in enumerate(lines):
            if line.strip().startswith("api_key = "):
                lines[index] = f'api_key = "{escaped_api_key}"'
                break
        else:
            raise SystemExit(f"Kimi config file missing api_key entry: {config_path}")
        config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _config_diagnostics(self, api_key: str | None) -> dict[str, object]:
        config_path = self._runtime_config_path()
        config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        return {
            "home": str(self._runtime_home()),
            "config_path": str(config_path),
            "config_exists": config_path.exists(),
            "config_size": len(config_text),
            "config_has_placeholder": "${KIMI_API_KEY}" in config_text,
            "config_has_api_key_entry": "api_key =" in config_text,
            "has_configured_api_key": bool(api_key),
            "api_key_fingerprint": self._api_key_fingerprint(api_key),
        }

    def _temporary_environment(self, settings) -> dict[str, str]:
        api_key = self._configured_api_key(settings)
        self._write_config_api_key(settings)
        environment = {}
        if api_key:
            environment["KIMI_API_KEY"] = api_key
            environment["MOONSHOT_API_KEY"] = api_key
        return environment

    def environment(self, settings) -> dict[str, str]:
        return self._temporary_environment(settings)

    def validate_config(self, settings) -> None:
        if not self._configured_api_key(settings):
            raise SystemExit(
                "Kimi API key is missing. Set agent.kimi_api_key to a real key or set KIMI_API_KEY."
            )

    def run(self, context: AgentExecutionContext) -> str:
        environment = self.environment(settings)
        api_key = self._configured_api_key(settings)
        diagnostics = self._config_diagnostics(api_key)
        if not shutil.which("kimi", path=os.environ.get("PATH")):
            log_event(
                logger,
                logging.ERROR,
                "agent.kimi.executable_missing",
                stage_name=context.stage_name,
                path=os.environ.get("PATH"),
                **diagnostics,
            )
            raise SystemExit("Kimi executable not found in PATH")
        command = [
            "kimi",
            "--prompt",
            context.prompt,
        ]
        if context.session_id:
            command[1:1] = ["--session", context.session_id]
        log_event(
            logger,
            logging.INFO,
            "agent.stage.command.start",
            stage_name=context.stage_name,
            engine=self.name,
            command=format_command(command),
            cwd=context.cwd,
            model=self._model_alias(),
            reasoning_effort=self.reasoning_effort,
            allowed_tools=self.allowed_tools,
            session_id=context.session_id,
            resume_session=context.resume_session,
            environment_keys=sorted(environment.keys()),
            **diagnostics,
        )
        version = context.run_subprocess(
            ["kimi", "--version"],
            step=f"agent:{context.stage_name}:kimi-version",
            cwd=context.cwd,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, **environment},
        )
        log_event(
            logger,
            logging.INFO,
            "agent.kimi.version",
            stage_name=context.stage_name,
            exit_code=version.returncode,
            stdout_tail=(version.stdout or "")[-400:],
            stderr_tail=(version.stderr or "")[-400:],
        )
        completed = context.run_subprocess(
            command,
            step=f"agent:{context.stage_name}",
            cwd=context.cwd,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, **environment},
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
                **diagnostics,
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
        return completed.stdout
