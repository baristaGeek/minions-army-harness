"""Claude Code agent provider."""

from __future__ import annotations

import json
import logging
import os

from minions_army.core.runtime.logging import format_command, log_event
from minions_army.infrastructure.agents.base import AgentExecutionContext, AgentProvider

logger = logging.getLogger("minions_army.agent_providers.claude")


class ClaudeAgentProvider(AgentProvider):
    name = "claude"
    model = "claude-haiku-4-5"
    reasoning_effort = "low"
    allowed_tools = "Bash,Read,Edit,Write,Glob,Grep"
    api_key_config_name = "anthropic_api_key"
    api_key_environment_variable = "ANTHROPIC_API_KEY"
    dspy_provider_name = "anthropic"

    def supports_shared_session(self) -> bool:
        return True

    def run(self, context: AgentExecutionContext) -> str:
        command = [
            "claude",
            "-p",
            context.prompt,
            "--model",
            self.model,
            "--effort",
            self.reasoning_effort,
            "--permission-mode",
            "bypassPermissions",
            "--output-format",
            "json",
            "--allowedTools",
            self.allowed_tools,
        ]
        if context.session_id:
            command.extend(
                ["--resume" if context.resume_session else "--session-id", context.session_id]
            )
        env = {**os.environ, "IS_SANDBOX": "1"}
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
            allowed_tools=self.allowed_tools,
            session_id=context.session_id,
            resume_session=context.resume_session,
        )
        completed = context.run_subprocess(
            command,
            step=f"agent:{context.stage_name}",
            cwd=context.cwd,
            check=False,
            capture_output=True,
            text=True,
            env=env,
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
        try:
            envelope = json.loads(completed.stdout)
        except json.JSONDecodeError:
            log_event(
                logger,
                logging.ERROR,
                "agent.stage.invalid_json",
                stage_name=context.stage_name,
                stdout_tail=(completed.stdout or "")[-1200:],
                stderr_tail=(completed.stderr or "")[-1200:],
            )
            raise SystemExit(
                f"Claude stage '{context.stage_name}' returned non-JSON output"
            ) from None
        if envelope.get("is_error"):
            log_event(
                logger,
                logging.ERROR,
                "agent.stage.error_envelope",
                stage_name=context.stage_name,
                envelope=envelope,
            )
            raise SystemExit(f"Claude stage '{context.stage_name}' returned an error")
        log_event(
            logger,
            logging.INFO,
            "agent.stage.command.succeeded",
            stage_name=context.stage_name,
            engine=self.name,
            exit_code=completed.returncode,
        )
        return str(envelope["result"])
