"""Pipeline step implementation."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from minions_army.application.services.orchestration_service import (
    PipelineContext,
)
from minions_army.core.config.loader import config as settings
from minions_army.core.runtime import orchestrator_runtime as runtime
from minions_army.core.runtime.logging import log_event

logger = logging.getLogger("minions_army.core.runtime.orchestrator_runtime")


@runtime._wrap_step_execute
@dataclass
class VerifyBuildStep:
    """Build/render gate. Runs before commit so a broken app never reaches a PR."""

    name: str = "verify-build"
    skip: bool = False

    def execute(self, context: PipelineContext) -> None:
        result = context.require_result()
        verify_cmd = settings.verification.command
        if not verify_cmd:
            log_event(
                logger,
                logging.INFO,
                "build.verify.skipped",
                reason="missing_verify_command",
            )
            return
        workdir = (result.repository_path / settings.verification.cwd).resolve()
        log_event(logger, logging.INFO, "build.verify.start", command=verify_cmd, cwd=workdir)
        completed = runtime.run_subprocess(
            ["bash", "-lc", verify_cmd],
            step="verify-build",
            cwd=workdir,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            log_event(
                logger,
                logging.ERROR,
                "build.verify.failed",
                command=verify_cmd,
                cwd=workdir,
                exit_code=completed.returncode,
                stdout_tail=(completed.stdout or "")[-1200:],
                stderr_tail=(completed.stderr or "")[-1200:],
            )
            runtime.post_slack(
                "??? Build/render check failed ??? not opening a PR.\n"
                + runtime._format_build_error(completed)
            )
            raise SystemExit("Build verification failed; skipping PR")
        log_event(
            logger,
            logging.INFO,
            "build.verify.succeeded",
            command=verify_cmd,
            cwd=workdir,
        )
