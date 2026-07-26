"""Pipeline step implementation."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from minions_army.application.services.orchestration_service import (
    OrchestrationResult,
    PipelineContext,
)
from minions_army.core.config.loader import config as settings
from minions_army.core.runtime import orchestrator_runtime as runtime
from minions_army.core.runtime.logging import format_command, log_event

logger = logging.getLogger("minions_army.core.runtime.orchestrator_runtime")


@runtime._wrap_step_execute
@dataclass
class ReviewMergeDeployStep:
    """A separate reviewer evaluates the PR; if approved, merge and deploy.

    The reviewer is an independent evaluator with a fresh context and a reviewer
    persona, so it is genuinely judging another agent's work rather than
    self-reviewing. Two engines produce the same verdict contract
    ``{approved, reasons, blocking_issues, risk_level}``:

    - ``claude_cli``: an agentic `claude -p` process that may run
      `gh pr view/diff` for extra context. Bound to Claude only.
    - ``agent`` (default): runs the review prompt through the configured agent
      provider. When that is the ``FallbackAgentProvider`` the reviewer inherits
      the Claude→Codex→Kimi chain, so it keeps reviewing and merging even when
      the primary provider is out of credits.
    - ``dspy``: a typed DSPy program calling the selected provider directly.
      Its prompt/few-shots can be optimized offline (see ``evals/``).
    """

    name: str = "review-merge-deploy"
    skip: bool = False

    def execute(self, context: PipelineContext) -> None:
        if not settings.reviewer.enabled:
            log_event(
                logger,
                logging.INFO,
                "review.skipped",
                reason="reviewer_disabled",
            )
            return
        result = context.require_result()

        diff_command = ["gh", "pr", "diff", result.work_branch]
        log_event(
            logger,
            logging.INFO,
            "review.diff.fetch.start",
            command=format_command(diff_command),
            work_branch=result.work_branch,
        )
        diff_completed = runtime.run_subprocess(
            diff_command,
            step="review-diff",
            cwd=result.repository_path,
            check=False,
            capture_output=True,
            text=True,
        )
        if diff_completed.returncode != 0:
            log_event(
                logger,
                logging.ERROR,
                "review.diff.fetch.failed",
                command=format_command(diff_command),
                cwd=result.repository_path,
                exit_code=diff_completed.returncode,
                stdout_tail=(diff_completed.stdout or "")[-1200:],
                stderr_tail=(diff_completed.stderr or "")[-1200:],
            )
            raise SystemExit(diff_completed.returncode)
        diff = diff_completed.stdout
        log_event(
            logger,
            logging.INFO,
            "review.diff.fetch.succeeded",
            work_branch=result.work_branch,
            diff_chars=len(diff),
        )

        engine = settings.reviewer.engine.lower().strip()
        if engine == "dspy":
            verdict = self._review_with_dspy(context, diff)
        elif engine == "claude_cli":
            verdict = self._review_with_claude_cli(context, result, diff)
        elif engine in {"agent", "fallback", "agent_fallback"}:
            verdict = self._review_with_agent(context, result, diff)
        else:
            raise SystemExit(
                f"Unsupported MINION_REVIEWER_ENGINE '{settings.reviewer.engine}'. "
                "Expected 'claude_cli', 'agent', or 'dspy'."
            )

        if not verdict.get("approved"):
            reasons = "; ".join(
                verdict.get("blocking_issues") or verdict.get("reasons") or ["unspecified"]
            )
            log_event(
                logger,
                logging.INFO,
                "review.rejected",
                engine=engine,
                reasons=reasons,
                verdict=verdict,
            )
            runtime.post_slack(f"⛔ Change needs human review: {reasons}")
            return

        log_event(
            logger,
            logging.INFO,
            "review.approved",
            engine=engine,
            verdict=verdict,
        )
        runtime.run_command(
            ["gh", "pr", "merge", result.work_branch, "--squash", "--delete-branch"],
            result.repository_path,
        )
        runtime.post_slack("✅ Reviewed & merged to main.")
        runtime._deploy(result)

    def _review_with_dspy(self, context: PipelineContext, diff: str) -> dict:
        # Imported lazily so the CLI reviewer path has no dspy dependency.
        from minions_army.infrastructure.reviewers import dspy as dspy_reviewer

        log_event(logger, logging.INFO, "review.dspy.start", diff_chars=len(diff))
        verdict = dspy_reviewer.review_pr(
            user_request=context.request.minion_input_message,
            pr_diff=diff,
        )
        log_event(
            logger,
            logging.INFO,
            "review.dspy.succeeded",
            verdict=verdict,
        )
        return verdict

    def _review_with_agent(
        self, context: PipelineContext, result: OrchestrationResult, diff: str
    ) -> dict:
        # Imported lazily to keep the step import light.
        from minions_army.infrastructure.agents.base import AgentExecutionContext

        review_prompt_file = runtime.PROMPT_ROOT / "openspec" / "review" / "prompt.md"
        if not review_prompt_file.exists():
            raise SystemExit(f"Review prompt file does not exist: {review_prompt_file}")

        prompt = review_prompt_file.read_text(encoding="utf-8")
        prompt = prompt.replace("{{WORK_BRANCH}}", result.work_branch)
        prompt = prompt.replace("{{MINION_INPUT_MESSAGE}}", context.request.minion_input_message)
        prompt = prompt.replace("{{PR_DIFF}}", diff)

        provider = runtime._agent_provider()
        # The whole diff is already inlined in the prompt, so the reviewer does
        # not depend on Claude-only `gh` tool wiring; any provider in the chain
        # can produce the verdict. Retry once for parse robustness, then fail
        # safe to "needs human review" rather than stranding the PR.
        attempts = 2
        for attempt in range(1, attempts + 1):
            exec_context = AgentExecutionContext(
                prompt=prompt,
                cwd=result.repository_path,
                stage_name="review",
                run_subprocess=runtime.run_subprocess,
            )
            log_event(
                logger,
                logging.INFO,
                "review.agent.start",
                provider=provider.name,
                model=settings.reviewer.model,
                work_branch=result.work_branch,
                diff_chars=len(diff),
                attempt=attempt,
                attempts=attempts,
            )
            try:
                raw_output = provider.run(exec_context)
            except SystemExit as exc:
                # The whole provider chain failed (e.g. every provider out of
                # credits). Retry, then fall through to the fail-safe verdict.
                log_event(
                    logger,
                    logging.WARNING if attempt < attempts else logging.ERROR,
                    "review.agent.provider_failed",
                    provider=provider.name,
                    attempt=attempt,
                    attempts=attempts,
                    error=str(exc.code),
                )
                continue
            verdict = runtime._extract_json_object(raw_output or "")
            if verdict is not None and "approved" in verdict:
                log_event(
                    logger,
                    logging.INFO,
                    "review.agent.succeeded",
                    provider=provider.name,
                    verdict=verdict,
                    attempt=attempt,
                )
                return verdict
            log_event(
                logger,
                logging.WARNING if attempt < attempts else logging.ERROR,
                "review.agent.unparsed",
                provider=provider.name,
                attempt=attempt,
                attempts=attempts,
                output_tail=(raw_output or "")[-1200:],
            )

        # Never merge on an unusable review; route to a human instead of crashing.
        return {
            "approved": False,
            "reasons": [],
            "blocking_issues": [
                f"Automated reviewer produced no usable verdict after {attempts} attempts "
                "(empty or unparseable output). Needs human review."
            ],
            "risk_level": "high",
        }

    def _review_with_claude_cli(
        self, context: PipelineContext, result: OrchestrationResult, diff: str
    ) -> dict:
        review_prompt_file = runtime.PROMPT_ROOT / "openspec" / "review" / "prompt.md"
        if not review_prompt_file.exists():
            raise SystemExit(f"Review prompt file does not exist: {review_prompt_file}")

        prompt = review_prompt_file.read_text(encoding="utf-8")
        prompt = prompt.replace("{{WORK_BRANCH}}", result.work_branch)
        prompt = prompt.replace("{{MINION_INPUT_MESSAGE}}", context.request.minion_input_message)
        prompt = prompt.replace("{{PR_DIFF}}", diff)

        command = [
            "claude",
            "-p",
            prompt,
            "--model",
            settings.reviewer.model,
            "--permission-mode",
            "bypassPermissions",
            "--output-format",
            "json",
            "--allowedTools",
            "Bash(gh pr view *),Bash(gh pr diff *),Read,Glob,Grep",
        ]

        # The agentic reviewer occasionally returns a non-zero exit, an empty
        # `result`, or JSON wrapped in prose (e.g. it exhausts its turns on a
        # large diff). None of those must crash the pipeline and strand the PR,
        # so retry once, then fail safe to "needs human review" below.
        attempts = 2
        for attempt in range(1, attempts + 1):
            log_event(
                logger,
                logging.INFO,
                "review.claude.start",
                command=format_command(command),
                model=settings.reviewer.model,
                work_branch=result.work_branch,
                diff_chars=len(diff),
                attempt=attempt,
                attempts=attempts,
            )
            completed = runtime.run_subprocess(
                command,
                step="review",
                cwd=result.repository_path,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "IS_SANDBOX": "1"},
            )
            verdict = runtime._parse_review_verdict(completed)
            if verdict is not None:
                log_event(
                    logger,
                    logging.INFO,
                    "review.claude.succeeded",
                    verdict=verdict,
                    attempt=attempt,
                )
                return verdict
            log_event(
                logger,
                logging.WARNING if attempt < attempts else logging.ERROR,
                "review.claude.unparsed",
                command=format_command(command),
                cwd=result.repository_path,
                attempt=attempt,
                attempts=attempts,
                exit_code=completed.returncode,
                stdout_tail=(completed.stdout or "")[-1200:],
                stderr_tail=(completed.stderr or "")[-1200:],
            )

        # Never merge on an unusable review; route to a human instead of crashing.
        return {
            "approved": False,
            "reasons": [],
            "blocking_issues": [
                f"Automated reviewer produced no usable verdict after {attempts} attempts "
                "(empty or unparseable output). Needs human review."
            ],
            "risk_level": "high",
        }
