"""Pipeline step implementation."""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from minions_army.application.services.orchestration_service import (
    AgentOutput,
    PipelineContext,
)
from minions_army.core.runtime import orchestrator_runtime as runtime
from minions_army.core.runtime.logging import log_event

logger = logging.getLogger("minions_army.core.runtime.orchestrator_runtime")


@runtime._wrap_step_execute
@dataclass
class PullRequestStep:
    name: str = "pr-create"
    skip: bool = False

    def execute(self, context: PipelineContext) -> None:
        result = context.require_result()
        outputs: dict[str, AgentOutput] = context.agent_outputs or {}
        implementation = outputs.get("implementation") or outputs.get("apply")
        if implementation is None:
            raise SystemExit("Implementation stage did not produce a response")
        pr_title = runtime._require_pr_title(implementation)
        pr_body = implementation.get("pr_body") or runtime._default_pr_body(context, implementation)
        body_file = Path(tempfile.gettempdir()) / "minions-army-pr-body.md"
        body_file.write_text(pr_body.rstrip() + "\n", encoding="utf-8")
        log_event(
            logger,
            logging.INFO,
            "pr.create.prepared",
            pr_title=pr_title,
            body_file=body_file,
            work_branch=result.work_branch,
        )
        runtime.run_command(
            [
                "gh",
                "pr",
                "create",
                "--title",
                pr_title,
                "--head",
                result.work_branch,
                "--body-file",
                str(body_file),
            ],
            result.repository_path,
        )
        runtime.post_slack(f"📝 PR opened: {pr_title}")
