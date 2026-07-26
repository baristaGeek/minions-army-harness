"""Tests for the minion orchestration service."""

from __future__ import annotations

from pathlib import Path

from minions_army.application.services.orchestration_service import (
    MinionOrchestrationService,
    OrchestrationRequest,
    OrchestrationResult,
)


def test_orchestration_service_delegates_to_pipeline_runner() -> None:
    request = OrchestrationRequest(
        repository_name="owner/repo",
        minion_input_message="hello",
        base_branch="main",
        feature_branch="feature/x",
        container_name="minion",
    )
    result = OrchestrationResult(repository_path=Path("/tmp/repo"), work_branch="feature/x")

    class FakePipelineRunner:
        def __init__(self) -> None:
            self.calls: list[OrchestrationRequest] = []

        def run(self, incoming_request: OrchestrationRequest) -> OrchestrationResult:
            self.calls.append(incoming_request)
            return result

    runner = FakePipelineRunner()
    service = MinionOrchestrationService(runner)

    returned = service.execute(request)

    assert returned == result
    assert runner.calls == [request]
