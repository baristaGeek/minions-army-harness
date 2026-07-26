"""Infrastructure adapters for minion orchestration."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from minions_army.application.services.orchestration_service import (
    AgentOutput,
    OrchestrationRequest,
    OrchestrationResult,
    PipelineContext,
    PipelineRunner,
    PipelineStep,
)
from minions_army.core.config.loader import config as settings
from minions_army.core.runtime.logging import (
    build_step_log_message,
    format_command,
    log_event,
    log_welcome_banner,
)
from minions_army.infrastructure.agents.loader import load_agent_provider
from minions_army.infrastructure.integrations.slack.notifier import post_slack_message
from minions_army.infrastructure.pipeline_steps.loader import load_pipeline_steps_provider

logger = logging.getLogger(__name__)
PROMPT_ROOT = Path("/opt/minions-army/execution/prompts")
CONSTITUTION_ROOT = Path("/opt/minions-army/execution/constitutions/core")

# Scaffolding the pipeline writes into the working tree during a run: the copied
# constitution, the OpenSpec/spec-kit working dirs, the agent-tool integration
# folders, and the per-stage prompt/output dumps. None of it is a product change,
# so CommitStep must keep every one of these paths out of the PR. .gitignore stops
# the untracked ones; the CommitStep guard also catches tracked files the pipeline
# overwrites (CONSTITUTION.md, .claude/*, .codex/*), which .gitignore cannot undo.
PIPELINE_ARTIFACT_PATHSPECS: tuple[str, ...] = (
    ".agent_prompts",
    ".agent-outputs",
    "openspec",  # openspec working dir
    ".openspec",
    ".specify",  # spec-kit working dir
    ".claude",  # openspec init --tools claude integration
    ".codex",  # spec-kit / codex integration
    "CONSTITUTION.md",
    ":(glob)**/CONSTITUTION.md",
)
OPENSPEC_SHARED_SESSION_STAGES = {"explore", "propose", "apply"}


def _agent_provider():
    return load_agent_provider(settings.agent.provider_class)


def _duration_ms_since(started_at_ns: int) -> int:
    return (time.perf_counter_ns() - started_at_ns) // 1_000_000


def _run_step_with_logging(
    context: PipelineContext, step_name: str, skip: bool, action: Callable[[], None]
) -> None:
    context.step_seq += 1
    step_seq = context.step_seq
    execution_id = context.execution_id
    if skip:
        logger.log(
            logging.INFO,
            build_step_log_message(
                step_name,
                "SKIPPED",
                0,
                execution_id=execution_id,
                step_seq=step_seq,
            ),
        )
        return

    logger.log(
        logging.INFO,
        build_step_log_message(
            step_name,
            "START",
            execution_id=execution_id,
            step_seq=step_seq,
        ),
    )
    started_at_ns = time.perf_counter_ns()
    try:
        action()
    except BaseException:
        logger.log(
            logging.INFO,
            build_step_log_message(
                step_name,
                "FAILED",
                _duration_ms_since(started_at_ns),
                execution_id=execution_id,
                step_seq=step_seq,
            ),
        )
        raise
    logger.log(
        logging.INFO,
        build_step_log_message(
            step_name,
            "END",
            _duration_ms_since(started_at_ns),
            execution_id=execution_id,
            step_seq=step_seq,
        ),
    )


def _wrap_step_execute(step_cls: type[PipelineStep]) -> type[PipelineStep]:
    original_execute = step_cls.execute

    def wrapped_execute(self: PipelineStep, context: PipelineContext) -> None:
        _run_step_with_logging(
            context,
            self.name,
            bool(getattr(self, "skip", False)),
            lambda: original_execute(self, context),
        )

    step_cls.execute = wrapped_execute  # type: ignore[assignment]
    return step_cls


def post_slack(text: str) -> None:
    """Post a progress message back to the originating webhook source."""
    post_slack_message(
        text,
        token=(
            settings.slack.bot_token
            or os.environ.get("MINION_SLACK_BOT_TOKEN")
            or os.environ.get("SLACK_BOT_TOKEN")
        ),
        channel=os.environ.get("SLACK_CHANNEL_ID"),
        thread_ts=os.environ.get("SLACK_EVENT_TS"),
    )


def run_subprocess(
    command: list[str],
    *,
    step: str,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """Run a subprocess and let callers handle non-zero exits."""
    return subprocess.run(command, **kwargs)


def _first_json_object(text: str) -> str | None:
    """Return the first balanced {...} block in text, or None."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_agent_output(raw_output: str, stage_name: str) -> AgentOutput:
    """Parse an agent stage's final message into the stage output dict.

    Claude's final message is not always pure JSON (it may narrate or be empty),
    so try the whole string, then an embedded {...} block, then fall back to a
    summary. Only the apply stage's fields are consumed downstream, and a summary
    is a sufficient fallback for the commit message and PR title.
    """
    text = (raw_output or "").strip().removeprefix("```json").removesuffix("```").strip()
    for candidate in (text, _first_json_object(text)):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed  # type: ignore[return-value]
    log_event(
        logger,
        logging.WARNING,
        "agent.output.summary_fallback",
        stage_name=stage_name,
    )
    return {"summary": text[:2000] or f"{stage_name} stage completed"}


def resolve_repository_url(repository_name: str) -> str:
    if repository_name.startswith(("http://", "https://", "git@")):
        return repository_name
    if "/" in repository_name:
        return f"https://github.com/{repository_name.removesuffix('.git')}.git"
    raise SystemExit(
        f"REPOSITORY_NAME must be a full Git URL or GitHub owner/repo, got: {repository_name}"
    )


def configure_git_auth(github_token: str | None) -> None:
    if not github_token:
        log_event(logger, logging.INFO, "git.auth.skipped", reason="missing_github_token")
        return
    os.environ.setdefault("GH_TOKEN", github_token)
    askpass = Path(tempfile.gettempdir()) / "git-askpass"
    askpass.write_text(
        '#!/bin/sh\ncase "$1" in\n    *Username*) echo "x-access-token" ;;\n    *Password*) echo "$GITHUB_TOKEN" ;;\n    *) echo "" ;;\nesac\n',
        encoding="utf-8",
    )
    askpass.chmod(0o700)
    os.environ["GIT_ASKPASS"] = str(askpass)
    os.environ["GIT_TERMINAL_PROMPT"] = "0"
    log_event(logger, logging.INFO, "git.auth.configured", askpass=askpass)


def run_command(
    command: list[str],
    cwd: Path,
    *,
    step: str | None = None,
) -> None:
    log_event(
        logger,
        logging.INFO,
        "subprocess.start",
        command=format_command(command),
        cwd=cwd,
    )
    completed = run_subprocess(
        command,
        step=step or " ".join(command[:2]),
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        log_event(
            logger,
            logging.ERROR,
            "subprocess.failed",
            command=format_command(command),
            cwd=cwd,
            exit_code=completed.returncode,
            stdout_tail=(completed.stdout or "")[-1200:],
            stderr_tail=(completed.stderr or "")[-1200:],
        )
        raise SystemExit(completed.returncode)
    log_event(
        logger,
        logging.INFO,
        "subprocess.succeeded",
        command=format_command(command),
        cwd=cwd,
        exit_code=completed.returncode,
    )


def _unstage_pipeline_artifacts(repository_path: Path) -> list[str]:
    """Drop pipeline scaffolding from the git index so it never reaches a PR.

    Runs right after ``git add -A``. ``git reset`` (not ``git rm``) is used so tracked
    files the pipeline overwrote (e.g. ``CONSTITUTION.md``, ``.claude/*``) are simply
    left unstaged instead of being deleted from the working tree. A non-zero exit from
    ``git reset -- <pathspec>`` only signals "paths still differ from HEAD" and is not a
    failure here, so it is logged rather than raised.

    Returns the artifact paths that were actually staged (and are now unstaged), for
    observability.
    """
    before = _staged_paths(repository_path)
    reset = subprocess.run(
        ["git", "reset", "-q", "--", *PIPELINE_ARTIFACT_PATHSPECS],
        cwd=repository_path,
        check=False,
        capture_output=True,
        text=True,
    )
    if reset.returncode != 0:
        log_event(
            logger,
            logging.INFO,
            "git.artifacts.unstage_note",
            exit_code=reset.returncode,
            stderr_tail=(reset.stderr or "")[-600:],
        )
    after = set(_staged_paths(repository_path))
    excluded = sorted(path for path in before if path not in after)
    if excluded:
        log_event(
            logger,
            logging.INFO,
            "git.artifacts.excluded",
            paths=excluded,
        )
    return excluded


def _staged_paths(repository_path: Path) -> list[str]:
    """Return the paths currently staged in the index (what a commit would include)."""
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=repository_path,
        check=False,
        capture_output=True,
        text=True,
    )
    return [line for line in staged.stdout.splitlines() if line.strip()]


def resolve_constitution_template_name(depth: str) -> str:
    templates = {
        "basic": "basic.md",
        "standard": "standard.md",
        "professional": "professional.md",
        "enterprise": "enterprise.md",
    }
    if depth not in templates:
        raise SystemExit(
            f"Unsupported MINION_CONSTITUTION_DEPTH '{depth}'. Expected one of: "
            + ", ".join(sorted(templates))
        )
    return templates[depth]


@dataclass(frozen=True)
class SpecFrameworkAdapter:
    name: str

    def stage_command(self, stage_name: str) -> str:
        if self.name == "speckit":
            commands = {
                "constitution": "/speckit-constitution",
                "specification": "/speckit.specify",
                "planner": "/speckit.plan",
                "tasks": "/speckit.tasks",
                "implementation": "/speckit.implement",
            }
        elif self.name == "openspec":
            commands = {
                "constitution": "openspec-constitution",
                "explore": "/opsx:explore",
                "propose": "/opsx:propose",
                "apply": "/opsx:apply",
            }
        else:
            raise SystemExit(
                f"Unsupported SPEC_FRAMEWORK '{self.name}'. Expected 'speckit' or 'openspec'."
            )
        if stage_name not in commands:
            raise SystemExit(f"Unsupported agent stage '{stage_name}' for framework '{self.name}'")
        return commands[stage_name]


def _extract_json_object(text: str) -> dict | None:
    """Parse a JSON object from model output that may be fenced or prose-wrapped.

    Tries the text as-is (after stripping ```json fences), then falls back to the
    first balanced ``{...}`` block anywhere in the string. Returns ``None`` when
    no JSON object can be recovered.
    """
    fenced = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    for candidate in (fenced, text):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
    return None


def _parse_review_verdict(completed: subprocess.CompletedProcess) -> dict | None:
    """Extract the ``{approved, ...}`` verdict from a ``claude -p --output-format
    json`` run, or return ``None`` when the reviewer produced nothing usable.

    Resilient to: non-zero exit, empty stdout, an error envelope (``is_error``),
    an empty ``result``, and a verdict wrapped in prose or ```json fences. The
    caller retries and, failing that, fails safe rather than raising.
    """
    if completed.returncode != 0:
        return None
    stdout = completed.stdout or ""
    if not stdout.strip():
        return None
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(envelope, dict) or envelope.get("is_error"):
        return None
    result_text = (envelope.get("result") or "").strip()
    if not result_text:
        return None
    verdict = _extract_json_object(result_text)
    if verdict is None or "approved" not in verdict:
        return None
    return verdict


def _deploy(result: OrchestrationResult) -> None:
    mode = settings.deploy.mode
    if mode in {"none", ""}:
        log_event(
            logger,
            logging.INFO,
            "deploy.skipped",
            reason="deploy_mode_none",
        )
        return
    if mode == "github_actions":
        log_event(
            logger,
            logging.INFO,
            "deploy.delegated",
            mode=mode,
        )
        return
    if mode == "flyctl":
        app = settings.launcher.fly_app
        if not app:
            raise SystemExit("MINION_FLY_APP is required for MINION_DEPLOY_MODE=flyctl")
        workdir = (result.repository_path / settings.verification.cwd).resolve()
        log_event(logger, logging.INFO, "deploy.flyctl.prepared", app=app, cwd=workdir)
        run_command(
            ["flyctl", "deploy", "--remote-only", "--app", app],
            workdir,
            step="deploy",
        )
        post_slack(f"ðŸš€ Deployed {app}.")
        return
    raise SystemExit(
        f"Unsupported MINION_DEPLOY_MODE '{mode}'. Expected 'flyctl', 'github_actions', or 'none'."
    )


def _format_build_error(completed: subprocess.CompletedProcess[str], max_lines: int = 15) -> str:
    """Return a Slack-friendly snippet of a failed build's output.

    Uses the tail of stderr (falling back to stdout) so the originating thread
    shows the actual compiler error (e.g. "Module not found: @/lib/db") without
    needing to read the Fly logs. Bounded so a huge build log can't flood Slack.
    """
    source = (completed.stderr or "").strip() or (completed.stdout or "").strip()
    if not source:
        return f"(no build output; exit code {completed.returncode})"
    tail = "\n".join(source.splitlines()[-max_lines:])[-1500:]
    return f"```\n{tail}\n```"


def _default_pr_body(context: PipelineContext, implementation: AgentOutput) -> str:
    lines = [
        "## Summary",
        str(implementation.get("summary", "")),
        "",
        "## Validation",
    ]
    validation = implementation.get("validation") or ["Not provided."]
    lines.extend(f"- {item}" for item in validation)
    lines.extend(["", "## Actions"])
    actions = implementation.get("actions") or ["Not provided."]
    lines.extend(f"- {item}" for item in actions)
    return "\n".join(lines)


def _require_pr_title(implementation: AgentOutput) -> str:
    pr_title = implementation.get("pr_title") or implementation.get("summary")
    if not pr_title:
        raise SystemExit("Implementation response is missing pr_title/summary")
    return pr_title


def _should_share_agent_session(spec_framework: str, stage_name: str) -> bool:
    return (
        _agent_provider().supports_shared_session()
        and spec_framework == "openspec"
        and stage_name in OPENSPEC_SHARED_SESSION_STAGES
    )


class SubprocessPipelineRunner(PipelineRunner):
    def run(self, request: OrchestrationRequest) -> OrchestrationResult:
        log_welcome_banner(logger)
        agent_provider = _agent_provider()
        log_event(
            logger,
            logging.INFO,
            "pipeline.start",
            repository=request.repository_name,
            base_branch=request.base_branch,
            feature_branch=request.feature_branch,
            container_name=request.container_name,
            spec_framework=request.spec_framework,
            agent_provider=agent_provider.name,
            agent_setup_tool=agent_provider.setup_tool_name(),
            **{
                "agent.provider_class": settings.agent.provider_class,
                "workflow.steps_provider_class": settings.workflow.steps_provider_class,
            },
        )
        steps_provider = load_pipeline_steps_provider(settings.workflow.steps_provider_class)
        context = PipelineContext(
            request=request,
            agent_outputs={},
            execution_id=uuid4().hex[:12],
        )
        pipeline = steps_provider.build()
        log_event(
            logger,
            logging.INFO,
            "pipeline.steps.selected",
            workflow_provider=getattr(steps_provider, "name", steps_provider.__class__.__name__),
            step_count=len(pipeline),
            steps=[getattr(step, "name", step.__class__.__name__) for step in pipeline],
            **{
                "workflow.steps_provider_class": settings.workflow.steps_provider_class,
            },
        )
        pipeline_started_at = time.perf_counter_ns()
        for step in pipeline:
            step.execute(context)
        result = context.require_result()
        total_duration_ms = (time.perf_counter_ns() - pipeline_started_at) // 1_000_000
        log_event(
            logger,
            logging.INFO,
            "pipeline.completed",
            total_duration_ms=total_duration_ms,
            work_branch=result.work_branch,
            repository_path=result.repository_path,
        )
        return result


def _require_agent_output(outputs: dict[str, AgentOutput], stage_name: str) -> AgentOutput:
    if stage_name not in outputs:
        raise SystemExit(f"Missing agent output for stage '{stage_name}'")
    return outputs[stage_name]
