"""Agent execution helpers used by pipeline steps."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import uuid4

from minions_army.application.services.orchestration_service import (
    AgentOutput,
    OrchestrationResult,
    PipelineContext,
)
from minions_army.core.runtime import orchestrator_runtime as runtime
from minions_army.core.runtime.logging import log_event
from minions_army.infrastructure.agents.base import AgentExecutionContext, AgentProvider

logger = logging.getLogger("minions_army.core.runtime.orchestrator_runtime")


def _build_agent_prompt(
    context: PipelineContext, result: OrchestrationResult, stage_name: str
) -> str:
    adapter = runtime.SpecFrameworkAdapter(context.request.spec_framework)
    prompt_file = runtime.PROMPT_ROOT / context.request.spec_framework / stage_name / "prompt.md"
    if not prompt_file.exists():
        raise SystemExit(f"Prompt file does not exist: {prompt_file}")
    stage_command = adapter.stage_command(stage_name)
    log_event(
        logger,
        logging.INFO,
        "agent.stage.prepared",
        stage_name=stage_name,
        spec_framework=context.request.spec_framework,
        stage_command=stage_command,
        prompt_file=prompt_file,
        repository_path=result.repository_path,
    )
    prompt = prompt_file.read_text(encoding="utf-8")
    if "{{MINION_INPUT_MESSAGE}}" in prompt:
        prompt = prompt.replace("{{MINION_INPUT_MESSAGE}}", context.request.minion_input_message)
    prompt = prompt.replace("{{REPOSITORY_NAME}}", context.request.repository_name)
    prompt = prompt.replace("{{WORK_BRANCH}}", result.work_branch)
    prompt = prompt.replace("{{SPEC_FRAMEWORK_NAME}}", context.request.spec_framework)
    prompt = prompt.replace("{{SPEC_STAGE_COMMAND}}", stage_command)
    prompt = prompt.replace(
        "{{CONSTITUTION_FILE}}", str(result.repository_path / "CONSTITUTION.md")
    )
    (result.repository_path / ".agent_prompts").mkdir(parents=True, exist_ok=True)
    (result.repository_path / ".agent-outputs").mkdir(parents=True, exist_ok=True)
    prompt_output_file = result.repository_path / ".agent_prompts" / f"{stage_name}.prompt.md"
    prompt_output_file.write_text(prompt.rstrip() + "\n", encoding="utf-8")
    log_event(
        logger,
        logging.INFO,
        "agent.prompt.rendered",
        stage_name=stage_name,
        prompt_path=prompt_output_file,
        prompt_chars=len(prompt),
    )
    return prompt


def _resolve_agent_session(context: PipelineContext, stage_name: str) -> tuple[str | None, bool]:
    session_id: str | None = None
    resume_session = False
    if runtime._should_share_agent_session(context.request.spec_framework, stage_name):
        resume_session = context.agent_session_id is not None
        if context.agent_session_id is None:
            context.agent_session_id = str(uuid4())
        session_id = context.agent_session_id
    return session_id, resume_session


def _execute_agent_strategy(
    *,
    prompt: str,
    cwd: Path,
    stage_name: str,
    session_id: str | None = None,
    resume_session: bool = False,
) -> str:
    provider: AgentProvider = runtime._agent_provider()
    context = AgentExecutionContext(
        prompt=prompt,
        cwd=cwd,
        stage_name=stage_name,
        run_subprocess=runtime.run_subprocess,
        session_id=session_id,
        resume_session=resume_session,
    )
    return provider.run(context)


def _store_agent_output(
    context: PipelineContext,
    result: OrchestrationResult,
    stage_name: str,
    raw_output: str,
) -> None:
    log_event(
        logger,
        logging.INFO,
        "agent.output.received",
        stage_name=stage_name,
        output_chars=len(raw_output or ""),
        output_preview=(raw_output or "")[:800],
    )
    data = runtime.parse_agent_output(raw_output, stage_name)
    outputs: dict[str, AgentOutput] = context.agent_outputs or {}
    outputs[stage_name] = data
    context.agent_outputs = outputs
    output_file = result.repository_path / ".agent-outputs" / f"{stage_name}.json"
    output_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    index_file = result.repository_path / ".agent-outputs" / "index.json"
    index_payload = context.agent_outputs or {}
    index_file.write_text(
        json.dumps(index_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    log_event(
        logger,
        logging.INFO,
        "agent.output.persisted",
        stage_name=stage_name,
        output_file=output_file,
        index_file=index_file,
        output_keys=sorted(data.keys()),
    )
    log_event(
        logger,
        logging.INFO,
        "agent.stage.completed",
        stage_name=stage_name,
        output_keys=sorted(data.keys()),
    )
