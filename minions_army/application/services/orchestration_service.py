"""Minion orchestration application service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypedDict


@dataclass(frozen=True)
class OrchestrationRequest:
    """Input required to run the minion workflow."""

    repository_name: str
    minion_input_message: str
    base_branch: str
    feature_branch: str
    container_name: str
    spec_framework: str = "speckit"
    github_token: str | None = None
    git_author_name: str = "Minions Army"
    git_author_email: str = "minions-army@local"


@dataclass(frozen=True)
class OrchestrationResult:
    """Summary of a completed orchestration run."""

    repository_path: Path
    work_branch: str


@dataclass
class PipelineContext:
    """Mutable execution state shared by pipeline steps."""

    request: OrchestrationRequest
    result: OrchestrationResult | None = None
    repository_url: str | None = None
    agent_outputs: dict[str, AgentOutput] | None = None
    agent_session_id: str | None = None
    execution_id: str | None = None
    step_seq: int = 0

    def require_result(self) -> OrchestrationResult:
        if self.result is None:
            raise SystemExit("Pipeline context is missing orchestration result")
        return self.result

    def require_repository_url(self) -> str:
        if not self.repository_url:
            raise SystemExit("Pipeline context is missing repository URL")
        return self.repository_url


class PipelineStep(Protocol):
    """A pipeline command that executes all of its own logic."""

    @property
    def name(self) -> str:
        """Stable step name used for ordering and logging."""

    def execute(self, context: PipelineContext) -> None:
        """Run the step and mutate the shared pipeline context if needed."""


class PipelineRunner(Protocol):
    """Executes the full pipeline, including deterministic and agent steps."""

    def run(self, request: OrchestrationRequest) -> OrchestrationResult:
        """Run all configured pipeline steps and return the final orchestration result."""


class AgentOutput(TypedDict, total=False):
    summary: str
    plan: str
    actions: list[str]
    validation: list[str]
    risks_follow_up: list[str]
    commit_message: str
    pr_title: str
    pr_body: str


class MinionOrchestrationService:
    """Coordinates repository preparation and agent execution."""

    def __init__(self, pipeline_runner: PipelineRunner) -> None:
        self.pipeline_runner = pipeline_runner

    def execute(self, request: OrchestrationRequest) -> OrchestrationResult:
        """Run the full minion workflow."""
        return self.pipeline_runner.run(request)
