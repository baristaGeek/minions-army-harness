"""Unit tests for the DSPy reviewer (offline, DummyLM — no network)."""

from __future__ import annotations

from types import SimpleNamespace

import dspy
import pytest
from dspy.utils.dummies import DummyLM

from minions_army.application.services.orchestration_service import (
    OrchestrationRequest,
    OrchestrationResult,
    PipelineContext,
)
from minions_army.core.runtime.steps.review_merge_deploy import ReviewMergeDeployStep
from minions_army.infrastructure.reviewers import dspy as dspy_reviewer
from minions_army.infrastructure.reviewers.dspy import ReviewPR, review_pr


def _dummy_program(answer: dict) -> dspy.Module:
    # ChainOfThought adds a `reasoning` field, so DummyLM must supply it.
    dspy.configure(lm=DummyLM([{"reasoning": "because", **answer}], reasoning=True))
    return dspy.ChainOfThought(ReviewPR)


def test_review_pr_returns_verdict_contract() -> None:
    program = _dummy_program(
        {"approved": True, "reasons": ["safe"], "blocking_issues": [], "risk_level": "low"}
    )
    verdict = review_pr("make heading blue", "benign diff", program=program, configure_lm=False)

    # Exact shape the pipeline's ReviewMergeDeployStep consumes.
    assert set(verdict) == {"approved", "reasons", "blocking_issues", "risk_level"}
    assert verdict["approved"] is True
    assert verdict["risk_level"] == "low"
    assert verdict["blocking_issues"] == []


def test_review_pr_blocks_dangerous_diff() -> None:
    program = _dummy_program(
        {
            "approved": False,
            "reasons": ["destructive"],
            "blocking_issues": ["DROP TABLE deletes data"],
            "risk_level": "high",
        }
    )
    verdict = review_pr("cleanup", "DROP TABLE Transaction", program=program, configure_lm=False)

    assert verdict["approved"] is False
    assert verdict["blocking_issues"]


def test_review_pr_truncates_oversized_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_program(user_request: str, pr_diff: str):
        captured["pr_diff"] = pr_diff
        return SimpleNamespace(approved=True, reasons=[], blocking_issues=[], risk_level="low")

    huge = "x" * (dspy_reviewer.MAX_DIFF_CHARS + 500)
    review_pr("req", huge, program=fake_program, configure_lm=False)

    assert len(captured["pr_diff"]) < len(huge)
    assert captured["pr_diff"].endswith("[diff truncated for length]")


def test_configure_reviewer_lm_uses_selected_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}

    class FakeLM:
        def __init__(self, model: str, api_key: str | None) -> None:
            captured["model"] = model
            captured["api_key"] = api_key

    monkeypatch.setattr(
        dspy_reviewer.settings.agent,
        "provider_class",
        "user_data.agent_providers.codex.CodexAgentProvider",
    )
    monkeypatch.setitem(dspy_reviewer.settings.agent.model_extra, "openai_api_key", "sk-openai")
    monkeypatch.setattr(dspy_reviewer.settings.reviewer, "model", "gpt-5.4-mini")
    monkeypatch.setattr(dspy_reviewer.dspy, "LM", FakeLM)
    monkeypatch.setattr(dspy_reviewer.dspy, "configure", lambda lm: captured.update(configured=lm))

    dspy_reviewer.configure_reviewer_lm()

    assert captured["model"] == "openai/gpt-5.4-mini"
    assert captured["api_key"] == "sk-openai"


def _make_context(tmp_path) -> PipelineContext:
    request = OrchestrationRequest(
        repository_name="owner/repo",
        minion_input_message="make heading blue",
        base_branch="main",
        feature_branch="feature/x",
        container_name="c1",
        spec_framework="openspec",
    )
    result = OrchestrationResult(repository_path=tmp_path, work_branch="feature/x_c1_abc")
    return PipelineContext(request=request, result=result, agent_outputs={})


def test_pipeline_uses_dspy_engine_and_merges_on_approve(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.reviewer.enabled", True
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.reviewer.engine", "dspy"
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.deploy.mode", "none"
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.subprocess.run",
        lambda command, **kwargs: SimpleNamespace(returncode=0, stdout="a diff", stderr=""),
    )
    # The dspy engine must be used instead of shelling out to `claude -p`.
    monkeypatch.setattr(
        dspy_reviewer,
        "review_pr",
        lambda user_request, pr_diff: {
            "approved": True,
            "reasons": ["ok"],
            "blocking_issues": [],
            "risk_level": "low",
        },
    )
    merges: list[list[str]] = []
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.run_command",
        lambda command, cwd: merges.append(command),
    )

    ReviewMergeDeployStep().execute(_make_context(tmp_path))

    assert merges and merges[0][0:3] == ["gh", "pr", "merge"]


def test_pipeline_dspy_engine_does_not_merge_on_reject(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.reviewer.enabled", True
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.reviewer.engine", "dspy"
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.subprocess.run",
        lambda command, **kwargs: SimpleNamespace(returncode=0, stdout="a diff", stderr=""),
    )
    monkeypatch.setattr(
        dspy_reviewer,
        "review_pr",
        lambda user_request, pr_diff: {
            "approved": False,
            "reasons": ["destructive"],
            "blocking_issues": ["DROP TABLE"],
            "risk_level": "high",
        },
    )
    merges: list[list[str]] = []
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.run_command",
        lambda command, cwd: merges.append(command),
    )

    ReviewMergeDeployStep().execute(_make_context(tmp_path))

    assert merges == []


def _ex(approved: bool, category: str = "benign"):
    return SimpleNamespace(approved=approved, category=category)


def _pred(approved: bool, blocking_issues=None):
    return SimpleNamespace(approved=approved, blocking_issues=blocking_issues or [])


def test_metric_penalizes_false_approval_hardest() -> None:
    from evals.metric import review_metric

    # Dangerous diff waved through -> 0.0 (worst case).
    assert review_metric(_ex(False, "destructive_sql"), _pred(True)) == 0.0
    # Correctly blocked and names the issue -> full credit.
    assert (
        review_metric(_ex(False, "destructive_sql"), _pred(False, ["DROP TABLE deletes data"]))
        == 1.0
    )
    # Benign approved -> 1.0; benign wrongly blocked -> mild 0.3.
    assert review_metric(_ex(True), _pred(True)) == 1.0
    assert review_metric(_ex(True), _pred(False)) == 0.3


def test_metric_bootstrap_mode_returns_bool() -> None:
    from evals.metric import review_metric

    # trace provided => optimization mode => strict bool.
    good = review_metric(_ex(False, "secret"), _pred(False, ["hardcoded api key"]), trace=object())
    bad = review_metric(_ex(False, "secret"), _pred(True), trace=object())
    assert good is True
    assert bad is False


def test_summarize_reports_error_rates() -> None:
    from evals.metric import summarize

    examples = [_ex(False, "secret"), _ex(True), _ex(False, "destructive_sql")]
    preds = [_pred(True), _pred(True), _pred(False, ["drop"])]  # one false approval
    stats = summarize(examples, preds)
    assert stats["n"] == 3
    assert stats["false_approve_rate"] == 0.5  # 1 of 2 dangerous approved
    assert stats["false_block_rate"] == 0.0
