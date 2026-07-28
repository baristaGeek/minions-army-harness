"""Contract tests for the repository's runtime wiring.

These guard the seams between files that Python imports cannot catch: the config
placeholders vs. the processes expected to supply them, the docs vs. the config
paths that are actually read, and the sample-app fixture vs. the verification
gate that compiles it.

Every test here corresponds to a defect that shipped in a release and broke the
documented setup path. They are cheap, hermetic, and need no network.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
API_CONFIG = REPO_ROOT / "user_data" / "api" / "config.yml"
ORCHESTRATOR_CONFIG = REPO_ROOT / "user_data" / "orchestrator" / "config.yml"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"

PLACEHOLDER_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")

SUPPORTED_REVIEWER_ENGINES = {"claude_cli", "agent", "fallback", "agent_fallback", "dspy"}


def _placeholders(path: Path) -> set[str]:
    """Return the ${VAR} names a config file expects from its environment.

    Walks the parsed YAML rather than the raw text so that a ${VAR} written in a
    comment (the files use one to explain the syntax) is not mistaken for a real
    requirement.
    """
    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, str):
            found.update(PLACEHOLDER_PATTERN.findall(node))
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(_load_yaml(path))
    return found


def _shipped_configs() -> list[Path]:
    paths = [API_CONFIG, ORCHESTRATOR_CONFIG]
    paths.extend(sorted((REPO_ROOT / "config_examples").glob("*.yml")))
    paths.append(REPO_ROOT / "user_data" / "config.example.yml")
    return [p for p in paths if p.exists()]


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _compose_api_env_keys() -> set[str]:
    """Env var names the compose `api` service defines, however they are valued."""
    compose = _load_yaml(COMPOSE_FILE)
    entries = compose["services"]["api"].get("environment") or []
    if isinstance(entries, dict):
        return set(entries)
    return {entry.split("=", 1)[0] for entry in entries}


# --- config placeholders vs. the processes that must supply them ------------


def test_compose_forwards_every_env_var_the_api_config_references() -> None:
    """A ${VAR} in the API config is dead unless compose puts VAR in the container.

    Regression: the api service forwarded only ANTHROPIC_API_KEY, so
    ${OPENAI_API_KEY} and ${KIMI_API_KEY} resolved to empty strings and the
    Claude -> Codex -> Kimi fallback chain silently degraded to Claude-only. A
    user whose Anthropic key was out of credit hit a hard stop, and the chain
    reported `missing_api_key` for keys that were in fact configured.
    """
    missing = sorted(_placeholders(API_CONFIG) - _compose_api_env_keys())
    assert not missing, (
        f"{API_CONFIG.relative_to(REPO_ROOT)} references {missing} but the compose "
        "`api` service does not define them, so they resolve to empty strings. "
        "Add them to the api service `environment:` block."
    )


def test_launcher_injects_every_env_var_the_minion_config_references(monkeypatch) -> None:
    """The minion gets config only through launcher-injected env vars.

    On Fly Machines there is no bind mount and no shell profile: every value
    arrives as an explicit `--env` flag built by the launcher. A placeholder the
    launcher does not set resolves to an empty string inside the machine.
    """
    from minions_army.domain.models import SlackMessage
    from minions_army.infrastructure.launchers import factory as launchers
    from user_data.agent_providers import kimi as kimi_provider

    # environment() materialises ~/.kimi-code/config.toml; keep the test hermetic.
    monkeypatch.setattr(kimi_provider.KimiAgentProvider, "_write_config_api_key", lambda *a: None)
    monkeypatch.setattr(
        launchers.settings.agent,
        "provider_class",
        "user_data.agent_providers.fallback.FallbackAgentProvider",
    )
    for key, value in (
        ("anthropic_api_key", "sk-ant-test"),
        ("openai_api_key", "sk-openai-test"),
        ("kimi_api_key", "sk-kimi-test"),
    ):
        monkeypatch.setitem(launchers.settings.agent.model_extra, key, value)
    monkeypatch.setattr(launchers.settings.repository, "name", "owner/repo")
    monkeypatch.setattr(launchers.settings.repository, "github_token", "gh-test")
    monkeypatch.setattr(launchers.settings.launcher, "fly_api_token", "fly-test")
    monkeypatch.setattr(launchers.settings.slack, "bot_token", "xoxb-test")

    runner = launchers.DockerSiblingTaskRunner()
    produced = set(
        runner._base_environment(
            SlackMessage(id=1, channel_id="C1", text="t", user_id="U1", slack_event_ts="1.0")
        )
    )

    missing = sorted(_placeholders(ORCHESTRATOR_CONFIG) - produced)
    assert not missing, (
        f"{ORCHESTRATOR_CONFIG.relative_to(REPO_ROOT)} references {missing}, but the "
        "launcher does not inject them into the minion, so they resolve to empty "
        "strings inside the container/machine."
    )


# --- docs vs. the config paths that are actually read ----------------------


def test_documented_default_config_paths_exist() -> None:
    """The API default and the minion's MINIONS_CONFIG_PATH must both resolve."""
    from minions_army.core.config.defaults import DEFAULT_USER_CONFIG

    assert (
        REPO_ROOT / DEFAULT_USER_CONFIG
    ).exists(), f"DEFAULT_USER_CONFIG points at {DEFAULT_USER_CONFIG}, which does not exist."

    dockerfile = (REPO_ROOT / "Dockerfile.minion").read_text(encoding="utf-8")
    match = re.search(r"MINIONS_CONFIG_PATH=(\S+)", dockerfile)
    assert match, "Dockerfile.minion no longer sets MINIONS_CONFIG_PATH"
    assert (REPO_ROOT / match.group(1)).exists(), (
        f"Dockerfile.minion sets MINIONS_CONFIG_PATH={match.group(1)}, "
        "which does not exist in the repo."
    )


def test_config_copy_instructions_point_at_a_config_that_is_read() -> None:
    """Docs must not tell contributors to create a config nothing reads.

    Regression: every guide said `cp user_data/config.example.yml
    user_data/config.yml`. Nothing reads that path -- the API reads
    user_data/api/config.yml and the minion reads
    user_data/orchestrator/config.yml -- so following the setup instructions
    produced a silently ignored file.
    """
    from minions_army.core.config.defaults import DEFAULT_USER_CONFIG

    readable = {
        str(DEFAULT_USER_CONFIG).replace("\\", "/"),
        "user_data/orchestrator/config.yml",
    }
    pattern = re.compile(
        r"(?:cp|Copy-Item)\s+user_data[/\\]config\.example\.yml\s+(\S+)",
        re.IGNORECASE,
    )

    offenders: list[str] = []
    for doc in sorted(REPO_ROOT.rglob("*.md")):
        if any(part in {"node_modules", ".venv", ".git"} for part in doc.parts):
            continue
        for destination in pattern.findall(doc.read_text(encoding="utf-8")):
            normalised = destination.replace("\\", "/").strip("`\"'")
            if normalised not in readable:
                offenders.append(f"{doc.relative_to(REPO_ROOT)} -> {destination}")

    assert not offenders, (
        "These docs tell the reader to create a config file that no process reads: "
        f"{offenders}. Point them at one of {sorted(readable)}."
    )


# --- the sample-app fixture vs. the verification gate ----------------------


def test_verification_cwd_exists_and_is_buildable() -> None:
    """The configured build gate must have something to build.

    Regression: sample-app shipped with no app/ or pages/ directory, so
    `npm ci && npm run build` failed on a clean checkout with "Couldn't find any
    `pages` or `app` directory". The Tier 1 demo only passed because the agent
    inferred it had to scaffold the entire app first; any request that did not
    happen to create app/ failed the gate.
    """
    verification = _load_yaml(ORCHESTRATOR_CONFIG).get("verification") or {}
    target = REPO_ROOT / (verification.get("cwd") or "sample-app")
    assert target.is_dir(), f"verification.cwd points at {target}, which is not a directory"

    package_json = target / "package.json"
    assert package_json.is_file(), f"{target.name} has no package.json to build"
    scripts = json.loads(package_json.read_text(encoding="utf-8")).get("scripts") or {}
    assert "build" in scripts, f"{target.name}/package.json defines no `build` script"

    routable = [d for d in (target / "app", target / "pages", target / "src" / "app") if d.is_dir()]
    assert routable, (
        f"{target.name} has no app/, pages/, or src/app/ directory, so `next build` "
        "fails with 'Couldn't find any `pages` or `app` directory'. The minion's "
        "verification gate runs this build on a clean checkout."
    )
    assert any(
        any(d.glob(f"page.{ext}")) or any(d.glob(f"index.{ext}"))
        for d in routable
        for ext in ("tsx", "ts", "jsx", "js")
    ), f"{routable[0].name}/ contains no page or index entry file, so no route is emitted"


def test_verification_command_uses_a_script_the_target_defines() -> None:
    """`npm run <script>` in verification.command must exist in package.json."""
    verification = _load_yaml(ORCHESTRATOR_CONFIG).get("verification") or {}
    command = verification.get("command") or ""
    target = REPO_ROOT / (verification.get("cwd") or "sample-app")
    package_json = target / "package.json"
    if not package_json.is_file():
        pytest.skip("no package.json in verification.cwd")

    scripts = json.loads(package_json.read_text(encoding="utf-8")).get("scripts") or {}
    referenced = set(re.findall(r"npm run ([A-Za-z0-9:_-]+)", command))
    missing = sorted(referenced - set(scripts))
    assert not missing, (
        f"verification.command runs {missing}, which {target.name}/package.json "
        "does not define; the gate would fail on every run."
    )


# --- reviewer and deploy wiring -------------------------------------------


@pytest.mark.parametrize("config_path", _shipped_configs(), ids=lambda p: p.name)
def test_shipped_configs_use_a_supported_reviewer_engine(config_path: Path) -> None:
    """An unknown reviewer engine is a SystemExit at the merge gate."""
    engine = ((_load_yaml(config_path).get("reviewer") or {}).get("engine") or "").strip().lower()
    if not engine:
        pytest.skip("config does not pin a reviewer engine")
    assert engine in SUPPORTED_REVIEWER_ENGINES, (
        f"{config_path.relative_to(REPO_ROOT)} sets reviewer.engine={engine!r}; "
        f"the step only accepts {sorted(SUPPORTED_REVIEWER_ENGINES)}."
    )


def test_reviewer_schema_default_is_a_supported_engine() -> None:
    from minions_army.core.config.schema import ReviewerConfig

    assert ReviewerConfig().engine in SUPPORTED_REVIEWER_ENGINES


def test_agent_reviewer_prompt_is_present_and_shipped() -> None:
    """The `agent` reviewer engine reads this prompt from the image at runtime.

    It is the only engine that inherits the Claude -> Codex -> Kimi chain, so it
    is the one to use when the reviewer must survive a provider outage. A missing
    prompt file is a SystemExit after the PR is already open.
    """
    prompt = REPO_ROOT / "execution" / "prompts" / "openspec" / "review" / "prompt.md"
    assert prompt.is_file(), f"{prompt.relative_to(REPO_ROOT)} is missing"
    assert prompt.read_text(encoding="utf-8").strip(), "review prompt is empty"

    dockerfile = (REPO_ROOT / "Dockerfile.minion").read_text(encoding="utf-8")
    assert "execution/prompts" in dockerfile, (
        "Dockerfile.minion no longer copies execution/prompts into the image, so the "
        "agent reviewer cannot find its prompt at runtime."
    )


@pytest.mark.parametrize("config_path", _shipped_configs(), ids=lambda p: p.name)
def test_flyctl_deploy_never_targets_the_orchestrators_own_app(config_path: Path) -> None:
    """`deploy.mode: flyctl` deploys verification.cwd, not this API.

    _deploy() runs `flyctl deploy --app <launcher.fly_app>` with the working
    directory set to verification.cwd, so pointing fly_app at the app defined in
    fly.toml makes an approved change deploy the target project over the
    orchestrator that launched it.
    """
    config = _load_yaml(config_path)
    mode = ((config.get("deploy") or {}).get("mode") or "").strip().lower()
    if mode != "flyctl":
        pytest.skip("deploy.mode is not flyctl")

    fly_app = ((config.get("launcher") or {}).get("fly_app") or "").strip()
    assert fly_app, "deploy.mode=flyctl requires launcher.fly_app"

    fly_toml = (REPO_ROOT / "fly.toml").read_text(encoding="utf-8")
    match = re.search(r"""(?m)^app\s*=\s*['"]([^'"]+)['"]""", fly_toml)
    own_app = match.group(1) if match else None
    assert fly_app != own_app, (
        f"{config_path.relative_to(REPO_ROOT)} would deploy verification.cwd to "
        f"{fly_app!r}, which is the orchestrator's own Fly app (fly.toml). The "
        "minion would overwrite the harness with the target project."
    )


def test_launcher_backends_named_in_configs_are_supported() -> None:
    """A typo'd backend is a SystemExit before any minion starts."""
    supported = {
        "docker",
        "fly_machines",
        "fly-machines",
        "fly",
        "cloud_jobs",
        "cloud-jobs",
        "cloud-jobs-run",
    }
    offenders = []
    for path in _shipped_configs():
        backend = ((_load_yaml(path).get("launcher") or {}).get("backend") or "").strip().lower()
        if backend and backend not in supported:
            offenders.append(f"{path.relative_to(REPO_ROOT)} -> {backend}")
    assert not offenders, f"unsupported launcher.backend values: {offenders}"


def test_agent_and_workflow_provider_classes_are_importable() -> None:
    """Provider classes are referenced as strings and resolved at runtime."""
    import importlib

    offenders = []
    for path in _shipped_configs():
        config = _load_yaml(path)
        references = [
            (config.get("agent") or {}).get("provider_class"),
            (config.get("workflow") or {}).get("steps_provider_class"),
        ]
        for reference in [r for r in references if r]:
            module_name, _, attribute = str(reference).rpartition(".")
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                offenders.append(f"{path.relative_to(REPO_ROOT)} -> {reference} (module)")
                continue
            if not hasattr(module, attribute):
                offenders.append(f"{path.relative_to(REPO_ROOT)} -> {reference} (attribute)")
    assert not offenders, f"config references unimportable provider classes: {offenders}"


def test_fallback_chain_default_covers_all_three_providers() -> None:
    """The README promises Claude -> Codex -> Kimi resilience by default."""
    from user_data.agent_providers.fallback import DEFAULT_PROVIDER_CHAIN

    assert [entry.rsplit(".", 1)[-1] for entry in DEFAULT_PROVIDER_CHAIN] == [
        "ClaudeAgentProvider",
        "CodexAgentProvider",
        "KimiAgentProvider",
    ]


def test_compose_mounted_config_paths_exist() -> None:
    """A stale bind-mount source silently shadows the config with a directory."""
    compose = _load_yaml(COMPOSE_FILE)
    offenders = []
    for volume in compose["services"]["api"].get("volumes") or []:
        if not isinstance(volume, str) or not volume.startswith("./"):
            continue
        source = volume.split(":", 1)[0]
        if not (REPO_ROOT / source[2:]).exists():
            offenders.append(source)
    assert not offenders, (
        f"docker-compose.yml bind-mounts paths that do not exist: {offenders}. "
        "Docker would create them as empty directories."
    )
