"""Tests for orchestrator runtime behavior."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from minions_army.application.services.orchestration_service import (
    OrchestrationRequest,
    OrchestrationResult,
    PipelineContext,
)
from minions_army.core.config.loader import config as settings
from minions_army.core.runtime.agent_execution import _execute_agent_strategy
from minions_army.core.runtime.orchestrator_runtime import (
    SpecFrameworkAdapter,
    SubprocessPipelineRunner,
    _default_pr_body,
    _deploy,
    _extract_json_object,
    _parse_review_verdict,
    _require_pr_title,
    _staged_paths,
    _unstage_pipeline_artifacts,
    _wrap_step_execute,
    configure_git_auth,
    post_slack,
    resolve_repository_url,
    run_command,
    run_subprocess,
)
from minions_army.core.runtime.steps.bootstrap import OpenSpecBootstrapStep, SpecKitBootstrapStep
from minions_army.core.runtime.steps.checkout_branch import CheckoutBranchStep
from minions_army.core.runtime.steps.clone_repository import CloneRepositoryStep
from minions_army.core.runtime.steps.commit import CommitStep
from minions_army.core.runtime.steps.configure_git import ConfigureGitStep
from minions_army.core.runtime.steps.constitution_preparation import ConstitutionPreparationStep
from minions_army.core.runtime.steps.openspec_apply import OpenspecApplyStep
from minions_army.core.runtime.steps.openspec_constitution import OpenspecConstitutionStep
from minions_army.core.runtime.steps.openspec_explore import OpenspecExploreStep
from minions_army.core.runtime.steps.openspec_propose import OpenspecProposeStep
from minions_army.core.runtime.steps.pull_request import PullRequestStep
from minions_army.core.runtime.steps.push import PushStep
from minions_army.core.runtime.steps.review_merge_deploy import ReviewMergeDeployStep
from minions_army.core.runtime.steps.speckit_tasks import SpeckitTasksStep
from minions_army.core.runtime.steps.verify_build import VerifyBuildStep
from user_data.pipeline_steps.openspec import OpenSpecPipelineStepsProvider
from user_data.pipeline_steps.speckit import SpecKitPipelineStepsProvider


def make_request(spec_framework: str = "speckit") -> OrchestrationRequest:
    return OrchestrationRequest(
        repository_name="owner/repo",
        minion_input_message="hello",
        base_branch="main",
        feature_branch="feature/x",
        container_name="minion",
        spec_framework=spec_framework,
        github_token="token-123",
        git_author_name="Minions Army",
        git_author_email="minions-army@local",
    )


def make_context(tmp_path: Path) -> PipelineContext:
    return PipelineContext(
        request=make_request(),
        result=OrchestrationResult(repository_path=tmp_path / "repo", work_branch="feature/x"),
        agent_outputs={},
        execution_id="exec-123",
    )


def test_resolve_repository_url_accepts_git_inputs() -> None:
    assert (
        resolve_repository_url("https://github.com/openai/minions-army.git")
        == "https://github.com/openai/minions-army.git"
    )
    assert resolve_repository_url("owner/repo") == "https://github.com/owner/repo.git"


def test_resolve_repository_url_rejects_invalid_values() -> None:
    with pytest.raises(SystemExit, match="REPOSITORY_NAME must be a full Git URL"):
        resolve_repository_url("invalid")


def test_configure_git_auth_sets_expected_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GIT_ASKPASS", raising=False)
    monkeypatch.delenv("GIT_TERMINAL_PROMPT", raising=False)

    configure_git_auth("token-123")

    assert os.environ["GH_TOKEN"] == "token-123"
    assert os.environ["GIT_TERMINAL_PROMPT"] == "0"
    assert Path(os.environ["GIT_ASKPASS"]).name == "git-askpass"


def test_run_command_raises_on_failure() -> None:
    failed = SimpleNamespace(returncode=2, stdout="out", stderr="err")

    with patch(
        "minions_army.core.runtime.orchestrator_runtime.subprocess.run", return_value=failed
    ):
        with pytest.raises(SystemExit, match="2"):
            run_command(["cmd"], Path("/tmp"))


def test_run_subprocess_returns_result() -> None:
    done = subprocess.CompletedProcess(args=["cmd"], returncode=0, stdout="ok", stderr="")
    with patch(
        "minions_army.core.runtime.orchestrator_runtime.subprocess.run", return_value=done
    ) as run:
        result = run_subprocess(["cmd"], step="x")

    assert result is done
    assert "timeout" not in run.call_args.kwargs


def test_pipeline_context_requires_result() -> None:
    context = PipelineContext(request=make_request())

    with pytest.raises(SystemExit, match="missing orchestration result"):
        context.require_result()


def test_pipeline_context_requires_repository_url() -> None:
    context = PipelineContext(request=make_request())

    with pytest.raises(SystemExit, match="missing repository URL"):
        context.require_repository_url()


def test_spec_framework_adapter_stage_commands() -> None:
    speckit = SpecFrameworkAdapter("speckit")
    openspec = SpecFrameworkAdapter("openspec")

    assert speckit.stage_command("constitution") == "/speckit-constitution"
    assert speckit.stage_command("tasks") == "/speckit.tasks"
    assert openspec.stage_command("constitution") == "openspec-constitution"
    assert openspec.stage_command("propose") == "/opsx:propose"
    assert openspec.stage_command("apply") == "/opsx:apply"

    with pytest.raises(SystemExit, match="Unsupported agent stage"):
        speckit.stage_command("unknown")


def test_openspec_pipeline_steps_provider_orders_steps() -> None:
    pipeline = OpenSpecPipelineStepsProvider().build()

    step_names = [
        getattr(step, "name", None) or getattr(step, "stage_name", None) for step in pipeline
    ]
    assert step_names == [
        "initialize-workspace",
        "clone",
        "checkout",
        "git-config",
        "constitution-prepare",
        "bootstrap",
        "openspec-constitution",
        "openspec-explore",
        "openspec-propose",
        "openspec-apply",
        "verify-build",
        "commit",
        "push",
        "pr-create",
        "review-merge-deploy",
    ]
    assert isinstance(pipeline[0], type(pipeline[0]))
    assert isinstance(pipeline[7], OpenspecExploreStep)
    assert pipeline[7].name == "openspec-explore"
    assert hasattr(pipeline[7], "skip")


def test_speckit_pipeline_steps_provider_orders_steps() -> None:
    pipeline = SpecKitPipelineStepsProvider().build()

    step_names = [
        getattr(step, "name", None) or getattr(step, "stage_name", None) for step in pipeline
    ]
    assert step_names == [
        "initialize-workspace",
        "clone",
        "checkout",
        "git-config",
        "constitution-prepare",
        "bootstrap",
        "speckit-constitution",
        "speckit-specification",
        "speckit-planner",
        "speckit-tasks",
        "speckit-implementation",
        "verify-build",
        "commit",
        "push",
        "pr-create",
        "review-merge-deploy",
    ]


def test_clone_step_executes_git_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    context = make_context(tmp_path)
    context.result = OrchestrationResult(repository_path=tmp_path / "repo", work_branch="feature/x")
    commands: list[list[str]] = []

    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.configure_git_auth",
        lambda token: commands.append(["auth", token or ""]),
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.resolve_repository_url",
        lambda repo: f"url:{repo}",
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.run_command",
        lambda command, cwd: commands.append(command),
    )

    CloneRepositoryStep().execute(context)

    assert commands[0] == ["auth", "token-123"]
    assert commands[1] == [
        "git",
        "clone",
        "--branch",
        "main",
        "--single-branch",
        "url:owner/repo",
        ".",
    ]


def test_checkout_and_configure_steps_execute_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = make_context(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.run_command",
        lambda command, cwd: calls.append(command),
    )

    CheckoutBranchStep().execute(context)
    ConfigureGitStep().execute(context)

    assert calls[0] == ["git", "checkout", "-b", "feature/x"]
    assert calls[1][0:3] == ["git", "config", "--global"]
    assert calls[2] == ["git", "config", "user.name", "Minions Army"]
    assert calls[3] == ["git", "config", "user.email", "minions-army@local"]


def test_bootstrap_steps_use_framework_specific_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    context = make_context(tmp_path)
    commands: list[list[str]] = []
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.agent.provider_class",
        "user_data.agent_providers.claude.ClaudeAgentProvider",
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.run_command",
        lambda command, cwd: commands.append(command),
    )

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        SpecKitBootstrapStep().execute(context)
        OpenSpecBootstrapStep().execute(context)

    assert commands[0][0:2] == ["specify", "init"]
    assert commands[1] == ["openspec", "init", "--tools", "claude", "--force"]
    assert "event=framework.bootstrap.prepared" in caplog.text
    assert "framework=speckit" in caplog.text
    assert "framework=openspec" in caplog.text
    assert "agent_provider=claude" in caplog.text
    assert "agent_setup_tool=claude" in caplog.text
    assert (
        "agent.provider_class=user_data.agent_providers.claude.ClaudeAgentProvider" in caplog.text
    )
    assert "workflow.steps_provider_class=" in caplog.text
    assert "bootstrap_tool=specify" in caplog.text
    assert "bootstrap_tool=openspec" in caplog.text


def test_constitution_preparation_step_copies_selected_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = make_context(tmp_path)
    context.result = OrchestrationResult(repository_path=tmp_path / "repo", work_branch="feature/x")
    source_root = tmp_path / "constitutions" / "core"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "professional.md").write_text("constitution content", encoding="utf-8")
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.CONSTITUTION_ROOT", source_root
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.workflow.constitution_depth",
        "professional",
    )
    (tmp_path / "repo").mkdir(parents=True, exist_ok=True)
    step = ConstitutionPreparationStep()

    step.execute(context)

    assert (tmp_path / "repo" / "CONSTITUTION.md").read_text(
        encoding="utf-8"
    ) == "constitution content"


def test_agent_step_writes_output_and_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = make_context(tmp_path)
    context.result = OrchestrationResult(repository_path=tmp_path / "repo", work_branch="feature/x")
    prompt_root = tmp_path / "prompts"
    prompt_file = prompt_root / "speckit" / "tasks" / "prompt.md"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(
        "Input={{MINION_INPUT_MESSAGE}} Branch={{WORK_BRANCH}} {{SPEC_FRAMEWORK_NAME}} {{SPEC_STAGE_COMMAND}} {{CONSTITUTION_FILE}}",
        encoding="utf-8",
    )
    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.PROMPT_ROOT", prompt_root)
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.agent.provider_class",
        "user_data.agent_providers.claude.ClaudeAgentProvider",
    )

    def fake_run(*args, **kwargs) -> SimpleNamespace:
        envelope = {
            "is_error": False,
            "result": (
                '{"summary":"done","plan":"plan","actions":["a"],'
                '"validation":["v"],"risks_follow_up":[]}'
            ),
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(envelope), stderr="")

    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.subprocess.run", fake_run)
    (tmp_path / "repo").mkdir(parents=True, exist_ok=True)
    (tmp_path / "repo" / ".agent_prompts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "repo" / "CONSTITUTION.md").write_text("constitution", encoding="utf-8")
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.workflow.constitution_depth",
        "standard",
    )
    step = SpeckitTasksStep()

    step.execute(context)

    assert context.agent_outputs["tasks"]["summary"] == "done"
    written_prompt = (tmp_path / "repo" / ".agent_prompts" / "tasks.prompt.md").read_text(
        encoding="utf-8"
    )
    assert "CONSTITUTION.md" in written_prompt


def test_commit_push_and_pr_steps_use_agent_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = make_context(tmp_path)
    context.result = OrchestrationResult(repository_path=tmp_path / "repo", work_branch="feature/x")
    context.agent_outputs = {
        "implementation": {
            "summary": "done",
            "plan": "plan",
            "actions": ["a"],
            "validation": ["v"],
            "risks_follow_up": [],
            "commit_message": "feat: done",
            "pr_title": "Add done",
            "pr_body": None,
        }
    }
    commands: list[list[str]] = []
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.run_command",
        lambda command, cwd: commands.append(command),
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.Path.write_text",
        lambda self, text, encoding=None: None,
    )
    # CommitStep checks `git status --porcelain` via subprocess.run; report changes.
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=" M sample-app/x", stderr=""),
    )

    CommitStep().execute(context)
    PushStep().execute(context)
    PullRequestStep().execute(context)

    assert commands[0] == ["git", "add", "-A"]
    assert commands[1] == ["git", "commit", "-m", "feat: done"]
    assert commands[2] == ["git", "push", "-u", "origin", "feature/x"]
    assert commands[3][0:3] == ["gh", "pr", "create"]


def test_default_pr_body_omits_pipeline_scaffolding_reference() -> None:
    context = PipelineContext(request=make_request())
    body = _default_pr_body(
        context,
        {
            "summary": "done",
            "validation": ["v1"],
            "actions": ["a1"],
        },
    )

    # The PR must not advertise pipeline scaffolding — it is never committed anymore.
    assert "## Agent Outputs" not in body
    assert ".agent-outputs/" not in body
    assert "## Summary" in body
    assert "## Validation" in body


def test_require_pr_title_prefers_pr_title_then_summary() -> None:
    assert _require_pr_title({"pr_title": "Add done", "summary": "done"}) == "Add done"
    assert _require_pr_title({"summary": "done"}) == "done"

    with pytest.raises(SystemExit, match="missing pr_title/summary"):
        _require_pr_title({})


def test_execute_agent_strategy_claude_parses_envelope_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.agent.provider_class",
        "user_data.agent_providers.claude.ClaudeAgentProvider",
    )
    captured: dict[str, list[str]] = {}

    def fake_run(command, *args, **kwargs):
        captured["command"] = command
        envelope = {"is_error": False, "result": "final text"}
        return SimpleNamespace(returncode=0, stdout=json.dumps(envelope), stderr="")

    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.subprocess.run", fake_run)

    output = _execute_agent_strategy(
        prompt="do it",
        cwd=Path("/repo"),
        stage_name="propose",
        session_id="session-123",
        resume_session=False,
    )

    assert output == "final text"
    assert captured["command"][0:2] == ["claude", "-p"]
    assert "--effort" in captured["command"]
    assert captured["command"][captured["command"].index("--effort") + 1] == "low"
    assert "--permission-mode" in captured["command"]
    assert "bypassPermissions" in captured["command"]
    assert "claude-haiku-4-5" in captured["command"]
    assert captured["command"][captured["command"].index("--allowedTools") + 1] == (
        "Bash,Read,Edit,Write,Glob,Grep"
    )
    assert "--session-id" in captured["command"]
    assert "session-123" in captured["command"]


def test_execute_agent_strategy_claude_raises_on_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.agent.provider_class",
        "user_data.agent_providers.claude.ClaudeAgentProvider",
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.subprocess.run",
        lambda *a, **k: SimpleNamespace(
            returncode=0, stdout=json.dumps({"is_error": True, "result": ""}), stderr=""
        ),
    )

    with pytest.raises(SystemExit, match="returned an error"):
        _execute_agent_strategy(
            prompt="p",
            cwd=Path("/repo"),
            stage_name="apply",
            session_id="session-123",
            resume_session=True,
        )


def test_execute_agent_strategy_codex_reads_response_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("user_data.agent_providers.codex._CODEX_LOGIN_READY", False)
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.agent.provider_class",
        "user_data.agent_providers.codex.CodexAgentProvider",
    )
    monkeypatch.setitem(settings.agent.model_extra, "openai_api_key", "sk-openai-test")
    calls: list[list[str]] = []

    def fake_run(command, *args, **kwargs):
        calls.append(command)
        if command[0:2] == ["codex", "logout"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if command[0:3] == ["codex", "login", "--with-api-key"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        assert command[0:2] == ["codex", "exec"]
        response_file = Path(command[command.index("--output-last-message") + 1])
        response_file.write_text("codex output", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.subprocess.run", fake_run)

    output = _execute_agent_strategy(
        prompt="p",
        cwd=Path("/repo"),
        stage_name="apply",
    )

    assert output == "codex output"
    assert calls[0][0:2] == ["codex", "logout"]
    assert calls[1][0:3] == ["codex", "login", "--with-api-key"]
    assert calls[2][0:2] == ["codex", "exec"]


def test_execute_agent_strategy_kimi_returns_quiet_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.agent.provider_class",
        "user_data.agent_providers.kimi.KimiAgentProvider",
    )
    monkeypatch.setenv("KIMI_API_KEY", "sk-kimi-test")
    monkeypatch.setitem(settings.agent.model_extra, "kimi_api_key", None)
    (tmp_path / "config.toml").write_text(
        'api_key = "${KIMI_API_KEY}"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "user_data.agent_providers.kimi.KimiAgentProvider._runtime_home",
        lambda self: tmp_path,
    )
    monkeypatch.setattr(
        "user_data.agent_providers.kimi.KimiAgentProvider._config_template_path",
        lambda self: tmp_path / "config.toml",
    )
    monkeypatch.setattr("user_data.agent_providers.kimi.shutil.which", lambda *a, **k: "kimi")
    captured: dict[str, object] = {}

    def fake_run(command, *args, **kwargs):
        if command == ["kimi", "--version"]:
            return SimpleNamespace(returncode=0, stdout="kimi 1.0.0", stderr="")
        captured["command"] = command
        captured["env"] = kwargs.get("env")
        return SimpleNamespace(returncode=0, stdout="kimi output", stderr="")

    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.subprocess.run", fake_run)

    output = _execute_agent_strategy(
        prompt="p",
        cwd=Path("/repo"),
        stage_name="apply",
        session_id="session-123",
        resume_session=True,
    )

    assert output == "kimi output"
    command = captured["command"]
    assert isinstance(command, list)
    assert command[0] == "kimi"
    assert "--auto" not in command
    assert command[command.index("--prompt") + 1] == "p"
    assert "--model" not in command
    assert command[command.index("--session") + 1] == "session-123"
    env = captured["env"]
    assert isinstance(env, dict)
    assert "KIMI_CODE_HOME" not in env
    assert env["KIMI_API_KEY"] == "sk-kimi-test"
    assert env["MOONSHOT_API_KEY"] == "sk-kimi-test"
    assert 'api_key = "sk-kimi-test"' in (tmp_path / "config.toml").read_text(encoding="utf-8")


def test_execute_agent_strategy_kimi_expands_api_key_placeholder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.agent.provider_class",
        "user_data.agent_providers.kimi.KimiAgentProvider",
    )
    monkeypatch.setitem(settings.agent.model_extra, "kimi_api_key", "${KIMI_API_KEY}")
    monkeypatch.setenv("KIMI_API_KEY", "sk-from-env")
    (tmp_path / "config.toml").write_text(
        'api_key = "${KIMI_API_KEY}"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "user_data.agent_providers.kimi.KimiAgentProvider._runtime_home",
        lambda self: tmp_path,
    )
    monkeypatch.setattr(
        "user_data.agent_providers.kimi.KimiAgentProvider._config_template_path",
        lambda self: tmp_path / "config.toml",
    )
    monkeypatch.setattr("user_data.agent_providers.kimi.shutil.which", lambda *a, **k: "kimi")

    def fake_run(command, *args, **kwargs):
        if command == ["kimi", "--version"]:
            return SimpleNamespace(returncode=0, stdout="kimi 1.0.0", stderr="")
        return SimpleNamespace(returncode=0, stdout="kimi output", stderr="")

    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.subprocess.run", fake_run)

    assert (
        _execute_agent_strategy(prompt="p", cwd=Path("/repo"), stage_name="apply") == "kimi output"
    )
    assert 'api_key = "sk-from-env"' in (tmp_path / "config.toml").read_text(encoding="utf-8")


def test_execute_agent_strategy_kimi_requires_api_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.agent.provider_class",
        "user_data.agent_providers.kimi.KimiAgentProvider",
    )
    monkeypatch.setitem(settings.agent.model_extra, "kimi_api_key", None)
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.setattr(
        "user_data.agent_providers.kimi.KimiAgentProvider._runtime_home",
        lambda self: tmp_path,
    )
    monkeypatch.setattr(
        "user_data.agent_providers.kimi.KimiAgentProvider._config_template_path",
        lambda self: tmp_path / "config.toml",
    )
    monkeypatch.setattr("user_data.agent_providers.kimi.shutil.which", lambda *a, **k: "kimi")

    with pytest.raises(SystemExit, match="Kimi API key is missing"):
        _execute_agent_strategy(prompt="p", cwd=Path("/repo"), stage_name="apply")


def test_execute_agent_strategy_kimi_logs_failure_details(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.agent.provider_class",
        "user_data.agent_providers.kimi.KimiAgentProvider",
    )
    monkeypatch.setenv("KIMI_API_KEY", "sk-kimi-test")
    monkeypatch.setitem(settings.agent.model_extra, "kimi_api_key", None)
    (tmp_path / "config.toml").write_text(
        'api_key = "${KIMI_API_KEY}"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "user_data.agent_providers.kimi.KimiAgentProvider._runtime_home",
        lambda self: tmp_path,
    )
    monkeypatch.setattr(
        "user_data.agent_providers.kimi.KimiAgentProvider._config_template_path",
        lambda self: tmp_path / "config.toml",
    )
    monkeypatch.setattr("user_data.agent_providers.kimi.shutil.which", lambda *a, **k: "kimi")

    def fake_run(command, *args, **kwargs):
        if command == ["kimi", "--version"]:
            return SimpleNamespace(returncode=0, stdout="kimi 1.0.0", stderr="")
        return SimpleNamespace(returncode=1, stdout="out", stderr="kimi failed")

    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.subprocess.run", fake_run)
    caplog.set_level(logging.INFO)

    with pytest.raises(SystemExit, match="1"):
        _execute_agent_strategy(prompt="p", cwd=Path("/repo"), stage_name="apply")

    assert "event=agent.stage.command.failed" in caplog.text
    assert "stderr_tail=kimi failed" in caplog.text
    assert "event=agent.kimi.version" in caplog.text
    assert "config_exists=True" in caplog.text
    assert "config_has_placeholder=False" in caplog.text
    assert "config_path=" in caplog.text


def test_execute_agent_strategy_logs_duration_on_success(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.agent.provider_class",
        "user_data.agent_providers.claude.ClaudeAgentProvider",
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.subprocess.run",
        lambda *a, **k: SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"is_error": False, "result": "final text"}),
            stderr="",
        ),
    )

    with caplog.at_level(logging.INFO, logger="minions_army.agent_providers.claude"):
        _execute_agent_strategy(
            prompt="do it",
            cwd=Path("/repo"),
            stage_name="explore",
        )

    assert "event=agent.stage.command.succeeded" in caplog.text
    assert "stage_name=explore" in caplog.text
    assert "duration_ms=" not in caplog.text


def test_run_command_logs_duration_on_success(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        run_command(["git", "status"], Path("/repo"))

    assert "event=subprocess.succeeded" in caplog.text
    assert "command=git status" in caplog.text
    assert "duration_ms=" not in caplog.text


def test_agent_stage_step_logs_completed_duration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    prompt_root = tmp_path / "prompts"
    prompt_file = prompt_root / "openspec" / "apply" / "prompt.md"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text("do {{REPOSITORY_NAME}}", encoding="utf-8")
    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.PROMPT_ROOT", prompt_root)
    monkeypatch.setattr(
        "minions_army.core.runtime.agent_execution._execute_agent_strategy",
        lambda **kwargs: json.dumps({"summary": "done", "actions": ["updated"]}),
    )
    context = PipelineContext(
        request=make_request("openspec"),
        result=OrchestrationResult(repository_path=tmp_path / "repo", work_branch="feature/x"),
        agent_outputs={},
        execution_id="exec-123",
    )

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        OpenspecApplyStep().execute(context)

    assert "[MINION][STEP][START] openspec-apply" in caplog.text
    assert "[MINION][STEP][END] openspec-apply" in caplog.text
    assert "event=agent.stage.completed" in caplog.text
    assert "stage_name=apply" in caplog.text
    assert "step_name=openspec-apply" in caplog.text
    assert "execution_id=exec-123" in caplog.text
    assert "step_seq=1" in caplog.text
    assert "duration_ms=" in caplog.text


def test_openspec_agent_steps_share_claude_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt_root = tmp_path / "prompts"
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "CONSTITUTION.md").write_text("constitution", encoding="utf-8")
    for stage_name in ("propose", "apply"):
        prompt_file = prompt_root / "openspec" / stage_name / "prompt.md"
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text("do {{REPOSITORY_NAME}}", encoding="utf-8")
    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.PROMPT_ROOT", prompt_root)
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.agent.provider_class",
        "user_data.agent_providers.claude.ClaudeAgentProvider",
    )

    calls: list[dict[str, object]] = []

    def fake_execute_agent_strategy(**kwargs):
        calls.append(kwargs)
        return json.dumps({"summary": kwargs["stage_name"], "actions": ["updated"]})

    monkeypatch.setattr(
        "minions_army.core.runtime.agent_execution._execute_agent_strategy",
        fake_execute_agent_strategy,
    )
    context = PipelineContext(
        request=make_request("openspec"),
        result=OrchestrationResult(repository_path=repo_root, work_branch="feature/x"),
        agent_outputs={},
        execution_id="exec-123",
    )

    OpenspecProposeStep().execute(context)
    OpenspecApplyStep().execute(context)

    assert len(calls) == 2
    assert calls[0]["stage_name"] == "propose"
    assert calls[0]["resume_session"] is False
    assert isinstance(calls[0]["session_id"], str)
    assert calls[1]["stage_name"] == "apply"
    assert calls[1]["resume_session"] is True
    assert calls[1]["session_id"] == calls[0]["session_id"]


def test_openspec_constitution_step_short_circuits_when_config_is_prepared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    repo_root = tmp_path / "repo"
    config_path = repo_root / "openspec" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                "schema: spec-driven",
                "",
                "context: |",
                "  # Example Repository",
                "",
                "  ## Tech Stack",
                "  - Python",
                "  - FastAPI",
                "",
                "  ## Architecture",
                "  Clean Architecture with explicit layers.",
                "",
                "  ## Component Boundaries",
                "  - Web API (`minions_army/infrastructure/api/`)",
                "",
                "  ## Engineering Standards",
                "  - Focused, reviewable changes",
                "",
                "rules:",
                "  proposal:",
                "    - Include acceptance criteria",
                "  implementation:",
                "    - Keep layer boundaries explicit",
            ]
        ),
        encoding="utf-8",
    )
    calls: list[str] = []
    monkeypatch.setattr(
        "minions_army.core.runtime.agent_execution._execute_agent_strategy",
        lambda **kwargs: calls.append("ran") or json.dumps({"summary": "should not run"}),
    )
    context = PipelineContext(
        request=make_request("openspec"),
        result=OrchestrationResult(repository_path=repo_root, work_branch="feature/x"),
        agent_outputs={},
        execution_id="exec-123",
    )

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        OpenspecConstitutionStep().execute(context)

    assert calls == []
    assert context.agent_outputs is not None
    assert context.agent_outputs["constitution"]["status"] == "skipped"
    assert context.agent_outputs["constitution"]["reason"] == "already_configured"
    assert "[MINION][STEP][START] openspec-constitution" in caplog.text
    assert "[MINION][STEP][END] openspec-constitution" in caplog.text
    assert "event=pipeline.step.START" in caplog.text
    assert "event=pipeline.step.END" in caplog.text
    output_file = repo_root / ".agent-outputs" / "constitution.json"
    assert output_file.exists()
    persisted = json.loads(output_file.read_text(encoding="utf-8"))
    assert persisted["status"] == "skipped"
    assert persisted["output_file"] == "openspec/config.yaml"


def test_openspec_constitution_step_does_not_short_circuit_for_default_like_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    prompt_root = tmp_path / "prompts"
    prompt_file = prompt_root / "openspec" / "constitution" / "prompt.md"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text("do {{REPOSITORY_NAME}}", encoding="utf-8")
    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.PROMPT_ROOT", prompt_root)

    repo_root = tmp_path / "repo"
    config_path = repo_root / "openspec" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")
    calls: list[dict[str, object]] = []

    def fake_execute_agent_strategy(**kwargs):
        calls.append(kwargs)
        return json.dumps({"summary": "configured", "actions": ["updated config"]})

    monkeypatch.setattr(
        "minions_army.core.runtime.agent_execution._execute_agent_strategy",
        fake_execute_agent_strategy,
    )
    context = PipelineContext(
        request=make_request("openspec"),
        result=OrchestrationResult(repository_path=repo_root, work_branch="feature/x"),
        agent_outputs={},
        execution_id="exec-123",
    )

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        OpenspecConstitutionStep().execute(context)

    assert len(calls) == 1
    assert calls[0]["stage_name"] == "constitution"
    assert context.agent_outputs is not None
    assert context.agent_outputs["constitution"]["summary"] == "configured"
    assert "[MINION][STEP][START] openspec-constitution" in caplog.text
    assert "[MINION][STEP][END] openspec-constitution" in caplog.text
    assert "event=pipeline.step.START" in caplog.text
    assert "event=pipeline.step.END" in caplog.text


def test_openspec_constitution_step_does_not_short_circuit_for_incomplete_realish_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt_root = tmp_path / "prompts"
    prompt_file = prompt_root / "openspec" / "constitution" / "prompt.md"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text("do {{REPOSITORY_NAME}}", encoding="utf-8")
    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.PROMPT_ROOT", prompt_root)

    repo_root = tmp_path / "repo"
    config_path = repo_root / "openspec" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                "schema: spec-driven",
                "context: |",
                "  Placeholder repo context",
                "rules:",
                "  proposal: []",
            ]
        ),
        encoding="utf-8",
    )
    calls: list[dict[str, object]] = []

    def fake_execute_agent_strategy(**kwargs):
        calls.append(kwargs)
        return json.dumps({"summary": "configured from incomplete config"})

    monkeypatch.setattr(
        "minions_army.core.runtime.agent_execution._execute_agent_strategy",
        fake_execute_agent_strategy,
    )
    context = PipelineContext(
        request=make_request("openspec"),
        result=OrchestrationResult(repository_path=repo_root, work_branch="feature/x"),
        agent_outputs={},
        execution_id="exec-123",
    )

    OpenspecConstitutionStep().execute(context)

    assert len(calls) == 1
    assert context.agent_outputs is not None
    assert context.agent_outputs["constitution"]["summary"] == "configured from incomplete config"


def test_openspec_constitution_step_injects_precomputed_context_into_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt_root = tmp_path / "prompts"
    prompt_file = prompt_root / "openspec" / "constitution" / "prompt.md"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(
        "Header\n{{PRECOMPUTED_REPOSITORY_CONTEXT}}\nFooter {{CONSTITUTION_FILE}}",
        encoding="utf-8",
    )
    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.PROMPT_ROOT", prompt_root)

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "CONSTITUTION.md").write_text("constitution", encoding="utf-8")
    (repo_root / "pyproject.toml").write_text(
        "[project]\nname='repo'\ndependencies=['fastapi']\n", encoding="utf-8"
    )
    (repo_root / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (repo_root / "next.config.ts").write_text("export default {}\n", encoding="utf-8")
    (repo_root / "apps" / "frontend-app").mkdir(parents=True, exist_ok=True)
    (repo_root / "apps" / "frontend-app" / "package.json").write_text(
        json.dumps(
            {
                "name": "frontend-app",
                "dependencies": {"next": "15.0.0", "react": "19.0.0"},
                "devDependencies": {"typescript": "5.0.0"},
            }
        ),
        encoding="utf-8",
    )
    (repo_root / "services" / "worker-service").mkdir(parents=True, exist_ok=True)
    calls: list[dict[str, object]] = []

    def fake_execute_agent_strategy(**kwargs):
        calls.append(kwargs)
        return json.dumps({"summary": "configured with precomputed context"})

    monkeypatch.setattr(
        "minions_army.core.runtime.agent_execution._execute_agent_strategy",
        fake_execute_agent_strategy,
    )
    context = PipelineContext(
        request=make_request("openspec"),
        result=OrchestrationResult(repository_path=repo_root, work_branch="feature/x"),
        agent_outputs={},
        execution_id="exec-123",
    )

    OpenspecConstitutionStep().execute(context)

    assert len(calls) == 1
    prompt = calls[0]["prompt"]
    assert "{{PRECOMPUTED_REPOSITORY_CONTEXT}}" not in prompt
    assert "Precomputed repository context:" in prompt
    assert "Detected languages: Python, TypeScript" in prompt
    assert "Detected frameworks: FastAPI, Next.js, React" in prompt
    assert "Detected tools: Docker Compose, pyproject.toml, package.json" in prompt
    assert "Candidate components:" in prompt
    written_prompt = (repo_root / ".agent_prompts" / "constitution.prompt.md").read_text(
        encoding="utf-8"
    )
    assert "Precomputed repository context:" in written_prompt
    assert "{{PRECOMPUTED_REPOSITORY_CONTEXT}}" not in written_prompt


def test_openspec_constitution_step_logs_end_when_agent_stage_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    prompt_root = tmp_path / "prompts"
    prompt_file = prompt_root / "openspec" / "constitution" / "prompt.md"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text("do {{REPOSITORY_NAME}}", encoding="utf-8")
    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.PROMPT_ROOT", prompt_root)

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    def fake_execute_agent_strategy(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "minions_army.core.runtime.agent_execution._execute_agent_strategy",
        fake_execute_agent_strategy,
    )
    context = PipelineContext(
        request=make_request("openspec"),
        result=OrchestrationResult(repository_path=repo_root, work_branch="feature/x"),
        agent_outputs={},
        execution_id="exec-123",
    )

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        with pytest.raises(RuntimeError, match="boom"):
            OpenspecConstitutionStep().execute(context)

    assert "[MINION][STEP][START] openspec-constitution" in caplog.text
    assert "[MINION][STEP][FAILED] openspec-constitution" in caplog.text
    assert "[MINION][STEP][END] openspec-constitution" in caplog.text
    assert "event=pipeline.step.START" in caplog.text
    assert "event=pipeline.step.FAILED" in caplog.text
    assert "event=pipeline.step.END" in caplog.text
    assert "duration_ms=" in caplog.text


def test_pipeline_runner_logs_constitution_start_and_end_for_short_circuit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    repo_root = tmp_path / "repo"
    config_path = repo_root / "openspec" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                "schema: spec-driven",
                "",
                "context: |",
                "  # Example Repository",
                "",
                "  ## Tech Stack",
                "  - Python",
                "  - FastAPI",
                "",
                "rules:",
                "  proposal:",
                "    - Include acceptance criteria",
                "  implementation:",
                "    - Keep layer boundaries explicit",
            ]
        ),
        encoding="utf-8",
    )

    @_wrap_step_execute
    class FakeInitStep:
        name = "initialize-workspace"
        skip = False

        def execute(self, context: PipelineContext) -> None:
            context.result = OrchestrationResult(repository_path=repo_root, work_branch="feature/x")

    class FakeStepsProvider:
        def build(self):
            return [FakeInitStep(), OpenspecConstitutionStep()]

    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.load_pipeline_steps_provider",
        lambda name: FakeStepsProvider(),
    )

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        SubprocessPipelineRunner().run(make_request("openspec"))

    assert "[MINION][STEP][START] openspec-constitution" in caplog.text
    assert "[MINION][STEP][END] openspec-constitution" in caplog.text
    assert "event=pipeline.step.START" in caplog.text
    assert "event=pipeline.step.END" in caplog.text


def test_pipeline_runner_skips_marked_steps(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    events: list[str] = []

    @_wrap_step_execute
    class FakeStep:
        def __init__(self, name: str, *, skip: bool = False) -> None:
            self.name = name
            self.skip = skip

        def execute(self, context: PipelineContext) -> None:
            events.append(self.name)
            if self.name == "initialize-workspace":
                context.result = OrchestrationResult(Path("/tmp/repo"), "feature/x")

    class FakeStepsProvider:
        def build(self):
            return [FakeStep("initialize-workspace"), FakeStep("explore", skip=True)]

    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.load_pipeline_steps_provider",
        lambda name: FakeStepsProvider(),
    )

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        SubprocessPipelineRunner().run(make_request("openspec"))

    assert events == ["initialize-workspace"]
    assert "[MINION][STEP][SKIPPED] explore" in caplog.text
    assert "event=pipeline.step.SKIPPED" in caplog.text
    assert "execution_id=" in caplog.text
    assert "step_seq=2" in caplog.text
    assert "step_name=explore" in caplog.text
    assert "duration_ms=0" in caplog.text


def test_verify_build_step_skips_when_command_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.verification.command", None
    )
    ran: list[str] = []
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.subprocess.run",
        lambda *a, **k: ran.append("ran") or SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        VerifyBuildStep().execute(make_context(tmp_path))

    assert ran == []
    assert "[MINION][STEP][START] verify-build" in caplog.text
    assert "[MINION][STEP][END] verify-build" in caplog.text
    assert "event=build.verify.skipped" in caplog.text
    assert "execution_id=exec-123" in caplog.text
    assert "step_seq=1" in caplog.text
    assert "duration_ms=" in caplog.text


def test_verify_build_step_aborts_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.verification.command",
        "npm run build",
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.verification.cwd", "sample-app"
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="build failed"),
    )

    with pytest.raises(SystemExit, match="Build verification failed"):
        VerifyBuildStep().execute(make_context(tmp_path))


def test_review_step_noop_when_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.reviewer.enabled", False
    )
    called: list[str] = []
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.subprocess.run",
        lambda *a, **k: called.append("ran"),
    )

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        ReviewMergeDeployStep().execute(make_context(tmp_path))

    assert called == []
    assert "[MINION][STEP][START] review-merge-deploy" in caplog.text
    assert "[MINION][STEP][END] review-merge-deploy" in caplog.text
    assert "event=review.skipped" in caplog.text
    assert "execution_id=exec-123" in caplog.text
    assert "step_seq=1" in caplog.text
    assert "duration_ms=" in caplog.text


def test_review_step_does_not_merge_on_reject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.reviewer.enabled", True
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.reviewer.engine", "claude_cli"
    )
    prompt_root = tmp_path / "prompts"
    review_file = prompt_root / "openspec" / "review" / "prompt.md"
    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text("review {{PR_DIFF}}", encoding="utf-8")
    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.PROMPT_ROOT", prompt_root)

    def fake_run(command, *args, **kwargs):
        if command[0:3] == ["gh", "pr", "diff"]:
            return SimpleNamespace(returncode=0, stdout="a diff", stderr="")
        envelope = {"result": '{"approved": false, "blocking_issues": ["drops a table"]}'}
        return SimpleNamespace(returncode=0, stdout=json.dumps(envelope), stderr="")

    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.subprocess.run", fake_run)
    merges: list[list[str]] = []
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.run_command",
        lambda command, cwd: merges.append(command),
    )

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        ReviewMergeDeployStep().execute(make_context(tmp_path))

    assert merges == []  # rejected -> never merged
    assert "[MINION][STEP][START] review-merge-deploy" in caplog.text
    assert "[MINION][STEP][END] review-merge-deploy" in caplog.text
    assert "event=review.diff.fetch.succeeded" in caplog.text
    assert "event=review.claude.succeeded" in caplog.text
    assert "event=review.rejected" in caplog.text
    assert "execution_id=exec-123" in caplog.text
    assert "step_seq=1" in caplog.text
    assert "duration_ms=" in caplog.text


class _FakeReviewProvider:
    """Stand-in for the agent provider used by the 'agent' reviewer engine."""

    name = "fallback"

    def __init__(self, *, result: str | None = None, fail: bool = False) -> None:
        self._result = result
        self._fail = fail
        self.calls = 0

    def run(self, context) -> str:
        self.calls += 1
        if self._fail:
            raise SystemExit(1)
        assert self._result is not None
        return self._result


def _setup_agent_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider) -> list:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.reviewer.enabled", True
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.reviewer.engine", "agent"
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.deploy.mode", "none"
    )
    prompt_root = tmp_path / "prompts"
    review_file = prompt_root / "openspec" / "review" / "prompt.md"
    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text("review {{PR_DIFF}}", encoding="utf-8")
    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.PROMPT_ROOT", prompt_root)

    def fake_run(command, *args, **kwargs):
        if command[0:3] == ["gh", "pr", "diff"]:
            return SimpleNamespace(returncode=0, stdout="a diff", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.subprocess.run", fake_run)
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime._agent_provider", lambda: provider
    )
    merges: list[list[str]] = []
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.run_command",
        lambda command, cwd: merges.append(command),
    )
    return merges


def test_review_step_agent_engine_merges_on_approve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    provider = _FakeReviewProvider(result='{"approved": true, "reasons": ["lgtm"]}')
    merges = _setup_agent_review(tmp_path, monkeypatch, provider)

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        ReviewMergeDeployStep().execute(make_context(tmp_path))

    assert merges[0][0:3] == ["gh", "pr", "merge"]
    assert "--squash" in merges[0]
    assert provider.calls == 1
    assert "event=review.agent.succeeded" in caplog.text
    assert "provider=fallback" in caplog.text


def test_review_step_agent_engine_fails_safe_when_chain_exhausted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    provider = _FakeReviewProvider(fail=True)  # every provider in the chain failed
    merges = _setup_agent_review(tmp_path, monkeypatch, provider)

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        ReviewMergeDeployStep().execute(make_context(tmp_path))

    assert merges == []  # never merge on an unusable review
    assert provider.calls == 2  # retried once before failing safe
    assert "event=review.agent.provider_failed" in caplog.text
    assert "event=review.rejected" in caplog.text


def test_review_step_agent_engine_fails_safe_on_unparsable_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    provider = _FakeReviewProvider(result="no verdict json here")
    merges = _setup_agent_review(tmp_path, monkeypatch, provider)

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        ReviewMergeDeployStep().execute(make_context(tmp_path))

    assert merges == []
    assert provider.calls == 2
    assert "event=review.agent.unparsed" in caplog.text
    assert "event=review.rejected" in caplog.text


def test_review_step_merges_and_deploys_on_approve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.reviewer.enabled", True
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.reviewer.engine", "claude_cli"
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.deploy.mode", "none"
    )
    prompt_root = tmp_path / "prompts"
    review_file = prompt_root / "openspec" / "review" / "prompt.md"
    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text("review", encoding="utf-8")
    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.PROMPT_ROOT", prompt_root)

    def fake_run(command, *args, **kwargs):
        if command[0:3] == ["gh", "pr", "diff"]:
            return SimpleNamespace(returncode=0, stdout="a diff", stderr="")
        envelope = {"result": '{"approved": true, "reasons": ["looks good"]}'}
        return SimpleNamespace(returncode=0, stdout=json.dumps(envelope), stderr="")

    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.subprocess.run", fake_run)
    merges: list[list[str]] = []
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.run_command",
        lambda command, cwd: merges.append(command),
    )

    ReviewMergeDeployStep().execute(make_context(tmp_path))

    assert merges[0][0:3] == ["gh", "pr", "merge"]
    assert "--squash" in merges[0]


def test_extract_json_object_handles_fences_and_prose() -> None:
    assert _extract_json_object('{"approved": true}') == {"approved": True}
    assert _extract_json_object('```json\n{"approved": false}\n```') == {"approved": False}
    assert _extract_json_object(
        'Here is my verdict:\n{"approved": true, "risk_level": "low"}\nThanks!'
    ) == {"approved": True, "risk_level": "low"}
    assert _extract_json_object("no json here at all") is None
    assert _extract_json_object("") is None


def test_parse_review_verdict_rejects_unusable_output() -> None:
    def completed(returncode=0, stdout="", stderr=""):
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    # non-zero exit / empty stdout / non-JSON envelope
    assert _parse_review_verdict(completed(returncode=1, stdout='{"result": "{}"}')) is None
    assert _parse_review_verdict(completed(stdout="   ")) is None
    assert _parse_review_verdict(completed(stdout="not json")) is None
    # error envelope and empty result
    assert (
        _parse_review_verdict(completed(stdout=json.dumps({"is_error": True, "result": "x"})))
        is None
    )
    assert _parse_review_verdict(completed(stdout=json.dumps({"result": ""}))) is None
    # valid result missing the required key
    assert (
        _parse_review_verdict(completed(stdout=json.dumps({"result": '{"reasons": []}'}))) is None
    )
    # well-formed verdict
    verdict = _parse_review_verdict(completed(stdout=json.dumps({"result": '{"approved": true}'})))
    assert verdict == {"approved": True}


def test_review_step_fails_safe_when_reviewer_output_unparsable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.reviewer.enabled", True
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.reviewer.engine", "claude_cli"
    )
    prompt_root = tmp_path / "prompts"
    review_file = prompt_root / "openspec" / "review" / "prompt.md"
    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text("review {{PR_DIFF}}", encoding="utf-8")
    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.PROMPT_ROOT", prompt_root)

    def fake_run(command, *args, **kwargs):
        if command[0:3] == ["gh", "pr", "diff"]:
            return SimpleNamespace(returncode=0, stdout="a diff", stderr="")
        # Reviewer returns an empty result on every attempt (the crash we saw).
        return SimpleNamespace(returncode=0, stdout=json.dumps({"result": ""}), stderr="")

    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.subprocess.run", fake_run)
    merges: list[list[str]] = []
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.run_command",
        lambda command, cwd: merges.append(command),
    )
    slack: list[str] = []
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.post_slack",
        lambda message: slack.append(message),
    )

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        # Must not raise, even though the reviewer never returned a verdict.
        ReviewMergeDeployStep().execute(make_context(tmp_path))

    assert merges == []  # unusable review -> never merged
    assert any("human review" in message for message in slack)
    assert "event=review.claude.unparsed" in caplog.text
    assert "event=review.rejected" in caplog.text
    assert "[MINION][STEP][END] review-merge-deploy" in caplog.text


def test_review_step_retries_and_merges_on_second_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.reviewer.enabled", True
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.reviewer.engine", "claude_cli"
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.deploy.mode", "none"
    )
    prompt_root = tmp_path / "prompts"
    review_file = prompt_root / "openspec" / "review" / "prompt.md"
    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text("review", encoding="utf-8")
    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.PROMPT_ROOT", prompt_root)

    claude_calls = {"n": 0}

    def fake_run(command, *args, **kwargs):
        if command[0:3] == ["gh", "pr", "diff"]:
            return SimpleNamespace(returncode=0, stdout="a diff", stderr="")
        claude_calls["n"] += 1
        if claude_calls["n"] == 1:
            # First attempt: empty result (transient failure).
            return SimpleNamespace(returncode=0, stdout=json.dumps({"result": ""}), stderr="")
        envelope = {"result": '{"approved": true, "reasons": ["looks good"]}'}
        return SimpleNamespace(returncode=0, stdout=json.dumps(envelope), stderr="")

    monkeypatch.setattr("minions_army.core.runtime.orchestrator_runtime.subprocess.run", fake_run)
    merges: list[list[str]] = []
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.run_command",
        lambda command, cwd: merges.append(command),
    )

    ReviewMergeDeployStep().execute(make_context(tmp_path))

    assert claude_calls["n"] == 2  # retried after the empty first attempt
    assert merges[0][0:3] == ["gh", "pr", "merge"]


def test_deploy_flyctl_runs_flyctl_deploy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.deploy.mode", "flyctl"
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.launcher.fly_app",
        "your-fly-app",
    )
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.verification.cwd", "sample-app"
    )
    commands: list[list[str]] = []
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.run_command",
        lambda command, cwd, **kwargs: commands.append(command),
    )

    _deploy(OrchestrationResult(repository_path=Path("/repo"), work_branch="feature/x"))

    assert commands[0][0:2] == ["flyctl", "deploy"]
    assert "your-fly-app" in commands[0]


def test_deploy_none_is_noop(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.settings.deploy.mode", "none"
    )
    commands: list[list[str]] = []
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.run_command",
        lambda command, cwd: commands.append(command),
    )

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        _deploy(OrchestrationResult(repository_path=Path("/repo"), work_branch="feature/x"))

    assert commands == []
    assert "event=deploy.skipped" in caplog.text
    assert "duration_ms=" not in caplog.text


def test_pipeline_runner_executes_pipeline_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    class FakeStep:
        def __init__(self, name: str) -> None:
            self.name = name

        def execute(self, context: PipelineContext) -> None:
            events.append(self.name)
            if self.name == "initialize-workspace":
                context.result = OrchestrationResult(Path("/tmp/repo"), "feature/x")

    class FakeStepsProvider:
        def build(self):
            return [FakeStep("initialize-workspace"), FakeStep("clone")]

    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.load_pipeline_steps_provider",
        lambda name: FakeStepsProvider(),
    )

    result = SubprocessPipelineRunner().run(make_request())

    assert events == ["initialize-workspace", "clone"]
    assert result.work_branch == "feature/x"


def test_pipeline_runner_logs_explicit_step_start_and_end(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    @_wrap_step_execute
    class FakeStep:
        def __init__(self, name: str) -> None:
            self.name = name

        def execute(self, context: PipelineContext) -> None:
            if self.name == "initialize-workspace":
                context.result = OrchestrationResult(Path("/tmp/repo"), "feature/x")

    class FakeStepsProvider:
        def build(self):
            return [FakeStep("initialize-workspace")]

    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.load_pipeline_steps_provider",
        lambda name: FakeStepsProvider(),
    )

    with caplog.at_level(logging.INFO, logger="minions_army.core.runtime.orchestrator_runtime"):
        SubprocessPipelineRunner().run(make_request())

    assert "__        __  _____  _      ____  ___  __  __  _____" in caplog.text
    assert '.-"""""""-.' in caplog.text
    assert "[MINION][STEP][START] initialize-workspace" in caplog.text
    assert "[MINION][STEP][END] initialize-workspace" in caplog.text
    assert "event=pipeline.step.START" in caplog.text
    assert "event=pipeline.step.END" in caplog.text
    assert "event=pipeline.start" in caplog.text
    assert "agent_provider=fallback" in caplog.text
    assert "agent_setup_tool=claude" in caplog.text
    assert (
        "agent.provider_class=user_data.agent_providers.fallback.FallbackAgentProvider"
        in caplog.text
    )
    assert "workflow.steps_provider_class=" in caplog.text
    assert "event=pipeline.steps.selected" in caplog.text
    assert "step_count=1" in caplog.text
    assert "execution_id=" in caplog.text
    assert "step_seq=1" in caplog.text
    assert "step_name=initialize-workspace" in caplog.text
    assert "state=START" in caplog.text
    assert "duration_ms=" in caplog.text


def test_parse_agent_output_extracts_embedded_json() -> None:
    from minions_army.core.runtime.orchestrator_runtime import parse_agent_output

    raw = 'Here is the result:\n```json\n{"summary": "did it", "actions": ["x"]}\n```\nDone.'
    data = parse_agent_output(raw, "apply")
    assert data["summary"] == "did it"


def test_parse_agent_output_falls_back_to_summary() -> None:
    from minions_army.core.runtime.orchestrator_runtime import parse_agent_output

    data = parse_agent_output("just prose, no json here", "constitution")
    assert "prose" in data["summary"]


def test_parse_agent_output_handles_empty() -> None:
    from minions_army.core.runtime.orchestrator_runtime import parse_agent_output

    data = parse_agent_output("", "explore")
    assert data["summary"] == "explore stage completed"


def test_commit_step_skips_when_no_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    context = make_context(tmp_path)
    context.agent_outputs = {"apply": {"summary": "done", "commit_message": "feat: x"}}
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.run_command", lambda command, cwd: None
    )
    # Empty porcelain -> no changes.
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    with pytest.raises(SystemExit, match="No changes to commit"):
        CommitStep().execute(context)


def _init_repo_like_writer_clone(repo: Path) -> None:
    """Build a real git repo that mirrors what the writer clones: a product tree
    with pipeline scaffolding (CONSTITUTION.md, .claude/) already tracked."""
    repo.mkdir(parents=True, exist_ok=True)

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)

    git("init", "-q")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@local")
    git("config", "commit.gpgsign", "false")
    # Ignore the untracked scaffolding, mirroring the repo's real .gitignore.
    (repo / ".gitignore").write_text(
        ".agent-outputs/\n.agent_prompts/\n/openspec/\nCONSTITUTION.md\n**/CONSTITUTION.md\n",
        encoding="utf-8",
    )
    (repo / "sample-app").mkdir()
    (repo / "sample-app" / "button.tsx").write_text("color: blue;\n", encoding="utf-8")
    # Scaffolding that is ALREADY tracked — .gitignore cannot exclude edits to these.
    (repo / "CONSTITUTION.md").write_text("old constitution\n", encoding="utf-8")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "config.md").write_text("old claude config\n", encoding="utf-8")
    git("add", "-A", "-f")  # force so the initial tracked-but-ignored files are committed
    git("commit", "-qm", "initial")


def test_commit_step_excludes_pipeline_artifacts_end_to_end(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo_like_writer_clone(repo)

    # Simulate a full pipeline run: a real product change plus every scaffolding artifact.
    (repo / "sample-app" / "button.tsx").write_text("color: red;\n", encoding="utf-8")  # the change
    (repo / "CONSTITUTION.md").write_text("regenerated constitution\n", encoding="utf-8")  # tracked
    (repo / ".claude" / "config.md").write_text("regenerated claude config\n", encoding="utf-8")
    (repo / ".claude" / "commands").mkdir()
    (repo / ".claude" / "commands" / "opsx.md").write_text("new\n", encoding="utf-8")  # untracked
    (repo / "openspec").mkdir()
    (repo / "openspec" / "config.yaml").write_text("openspec: {}\n", encoding="utf-8")
    (repo / ".agent_prompts").mkdir()
    (repo / ".agent_prompts" / "apply.prompt.md").write_text("prompt\n", encoding="utf-8")
    (repo / ".agent-outputs").mkdir()
    (repo / ".agent-outputs" / "apply.json").write_text("{}\n", encoding="utf-8")

    context = make_context(tmp_path)
    context.result = OrchestrationResult(repository_path=repo, work_branch="feature/x")
    context.agent_outputs = {"apply": {"summary": "recolor button", "commit_message": "feat: red"}}

    CommitStep().execute(context)

    committed = subprocess.run(
        ["git", "show", "--name-only", "--pretty=format:", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()

    assert committed == ["sample-app/button.tsx"], f"unexpected files in commit: {committed}"
    for artifact in (
        "CONSTITUTION.md",
        ".claude/config.md",
        ".claude/commands/opsx.md",
        "openspec/config.yaml",
        ".agent_prompts/apply.prompt.md",
        ".agent-outputs/apply.json",
    ):
        assert artifact not in committed
    # The scaffolding must survive on disk (guard unstages, never deletes).
    assert (repo / "CONSTITUTION.md").read_text(encoding="utf-8") == "regenerated constitution\n"


def test_commit_step_aborts_when_only_scaffolding_changed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo_like_writer_clone(repo)

    # Only scaffolding changed — no real product change. Must not open an empty PR.
    (repo / "CONSTITUTION.md").write_text("regenerated\n", encoding="utf-8")
    (repo / "openspec").mkdir()
    (repo / "openspec" / "config.yaml").write_text("openspec: {}\n", encoding="utf-8")

    context = make_context(tmp_path)
    context.result = OrchestrationResult(repository_path=repo, work_branch="feature/x")
    context.agent_outputs = {"apply": {"summary": "noop", "commit_message": "feat: noop"}}

    with patch("minions_army.core.runtime.orchestrator_runtime.post_slack"):
        with pytest.raises(SystemExit, match="No changes to commit"):
            CommitStep().execute(context)


def test_unstage_pipeline_artifacts_reports_excluded_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo_like_writer_clone(repo)
    (repo / "sample-app" / "button.tsx").write_text("color: red;\n", encoding="utf-8")
    # Both are tracked scaffolding, so `git add -A` stages them regardless of .gitignore
    # — exactly the case the guard exists to catch.
    (repo / "CONSTITUTION.md").write_text("regenerated\n", encoding="utf-8")
    (repo / ".claude" / "config.md").write_text("regenerated\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True, text=True)
    excluded = _unstage_pipeline_artifacts(repo)

    assert "CONSTITUTION.md" in excluded
    assert ".claude/config.md" in excluded
    assert _staged_paths(repo) == ["sample-app/button.tsx"]


def test_post_slack_posts_only_to_slack_for_slack_source(monkeypatch) -> None:
    slack_calls: list[dict[str, object]] = []
    monkeypatch.setenv("MINION_WEBHOOK_SOURCE", "slack")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    monkeypatch.setenv("SLACK_EVENT_TS", "1.2")
    monkeypatch.setattr(
        "minions_army.core.runtime.orchestrator_runtime.post_slack_message",
        lambda *args, **kwargs: slack_calls.append(kwargs),
    )

    post_slack("Reviewed & merged to main.")

    assert slack_calls == [
        {
            "token": settings.slack.bot_token,
            "channel": "C123",
            "thread_ts": "1.2",
        }
    ]
