# Configuration Guide

Minions Army is configured from YAML; do not duplicate static configuration as launcher
environment variables.

Two processes read two different files, both already checked into the repo:

| File | Read by | How it is resolved |
|------|---------|--------------------|
| `user_data/api/config.yml` | the API | default (`DEFAULT_USER_CONFIG`), mounted by `docker-compose.yml` |
| `user_data/orchestrator/config.yml` | the minion | `MINIONS_CONFIG_PATH` in `Dockerfile.minion` |

Either can be overridden with the `MINIONS_CONFIG_PATH` environment variable, or with `--config` on
the `minion-orchestrator` entrypoint. Note that `user_data/config.yml` is not read by anything —
copying the example there has no effect.

## Quick Start

1. Edit the config in place, or start from the example:

```bash
cp user_data/config.example.yml user_data/api/config.yml
```

On Windows PowerShell:

```powershell
Copy-Item user_data\config.example.yml user_data\api\config.yml
```

2. Fill in concrete values.

```yaml
database:
  url: postgresql+asyncpg://user:password@host:5432/minions_army

repository:
  name: owner/repo
  github_token: ghp_your_github_token

agent:
  provider_class: user_data.agent_providers.claude.ClaudeAgentProvider
  anthropic_api_key: sk-ant-your-anthropic-key
```

3. Build and run the API/minion image after config changes.

```bash
docker-compose build
docker-compose up -d
```

For Fly minion images, rebuild and push the minion image whenever
`user_data/orchestrator/config.yml`, providers, or pipeline definitions change.

## Config Ownership Rule

The two config files above are the source of truth for runtime configuration. For
remote minion images, prefer concrete values in `user_data/orchestrator/config.yml`
because `user_data/` is copied into the image at build time.

YAML placeholders such as `${DATABASE_URL}` and `${GITHUB_TOKEN}` are supported
by the loader, but they only work when those variables are present in the
process that loads the config. If a minion image contains placeholders, the
minion runtime must receive those same environment variables or the placeholders
resolve to empty strings.

This keeps the config contract simple:

- Static settings should live in the config file for the process that reads them.
- The minion image copies `user_data/` into `/app/user_data`.
- The minion reads `/app/user_data/orchestrator/config.yml` on startup.
- The launcher should not reconstruct static config as environment variables.

Environment variables are only used at hard runtime boundaries:

- Dynamic execution input: `MINION_INPUT_MESSAGE`, `MINION_CONTAINER_NAME`, and
  Slack thread context.
- CLI auth variables required by third-party CLIs. Providers derive these from
  their declared `api_key_config_name`.
- Parent process auth needed to launch external infrastructure, such as
  `FLY_API_TOKEN` for the `flyctl machine run` subprocess.

## Core Config Sections

### `app`

```yaml
app:
  name: minions-army
  environment: development
  debug: false
```

Controls application identity, logging/debug behavior, and labels.

### `database`

```yaml
database:
  url: postgresql+asyncpg://user:password@host:5432/minions_army
  sync_url:
```

`url` is required. Use an async SQLAlchemy URL for the app. `sync_url` is
optional; migrations derive a synchronous URL when it is omitted.

### `slack`

```yaml
slack:
  allowed_channel_id: C1234567890
  bot_token: xoxb-your-slack-bot-token
```

`allowed_channel_id` is optional. If set, only messages from that channel are
accepted.

`bot_token` is used by the API/launcher and by the minion runtime when posting
progress back to Slack.

Slack message-specific values such as the source channel, user, and thread
timestamp are not config. They are dynamic execution context passed when a
minion starts.

### `repository`

```yaml
repository:
  name: owner/repo
  base_branch: main
  feature_branch: feature/minion-task
  github_token: ghp_your_github_token
```

`github_token` comes from config. During clone/push/PR operations, the runtime
sets the subprocess environment required by `git` and `gh` from this configured
value.

### `agent`

```yaml
agent:
  provider_class: user_data.agent_providers.claude.ClaudeAgentProvider
  anthropic_api_key: sk-ant-your-anthropic-key
```

`provider_class` is a Python class path. Each provider declares the agent config
key it reads through `api_key_config_name`.

Built-in user providers:

| Provider | Class | Config key |
| --- | --- | --- |
| Claude | `user_data.agent_providers.claude.ClaudeAgentProvider` | `agent.anthropic_api_key` |
| Codex | `user_data.agent_providers.codex.CodexAgentProvider` | `agent.openai_api_key` |
| Kimi | `user_data.agent_providers.kimi.KimiAgentProvider` | `agent.kimi_api_key` |

### `workflow`

```yaml
workflow:
  steps_provider_class: user_data.pipeline_steps.openspec.OpenSpecPipelineStepsProvider
  constitution_depth: standard
```

`steps_provider_class` selects the pipeline. Existing options are:

- `user_data.pipeline_steps.openspec.OpenSpecPipelineStepsProvider`
- `user_data.pipeline_steps.speckit.SpecKitPipelineStepsProvider`

`constitution_depth` selects the engineering constitution template:
`basic`, `standard`, `professional`, or `enterprise`.

### `launcher`

```yaml
launcher:
  backend: fly_machines
  image: registry.fly.io/minions-army-minion:latest
  codex_home:
  cloud_run_project:
  cloud_run_region:
  cloud_run_job_name: minions-army-minion
  fly_machine_app: minions-army-minion
  fly_app: minions-army
  fly_region: fra
  fly_api_token: fly_your_token
  fly_vm_memory: 2048
  fly_vm_cpus: 2
```

`backend` can be:

- `docker`
- `fly_machines`
- `cloud_jobs`

`fly_api_token` is read from config. The launcher passes it only to the parent
`flyctl` subprocess that creates the machine; it is not copied as static minion
config.

`codex_home` is optional compatibility for Codex local config. API-key auth is
preferred through `agent.openai_api_key`.

### `verification`

```yaml
verification:
  command: npm ci && npm run build
  cwd: sample-app
```

The command runs after implementation to verify the target project.

### `reviewer`

```yaml
reviewer:
  enabled: false
  model: claude-haiku-4-5
  engine: claude_cli
  compiled_path:
```

When enabled, the review step can run an automated reviewer before merge/deploy.

### `deploy`

```yaml
deploy:
  mode: none
```

Supported modes:

- `none`
- `flyctl`
- `github_actions`

For `flyctl`, `launcher.fly_app` is required. The deploy subprocess receives
`FLY_API_TOKEN` derived from `launcher.fly_api_token`.

## Provider Examples

Complete example files are available in `config_examples/`:

- `config_examples/minimal.yml`
- `config_examples/slack_github_claude.yml`
- `config_examples/codex.yml`
- `config_examples/kimi.yml`

### Claude

```yaml
agent:
  provider_class: user_data.agent_providers.claude.ClaudeAgentProvider
  anthropic_api_key: sk-ant-your-anthropic-key
```

Requires Claude Code CLI in the minion image. The provider runs `claude -p` with
JSON output and bypass permissions.

### Codex

```yaml
agent:
  provider_class: user_data.agent_providers.codex.CodexAgentProvider
  openai_api_key: sk-your-openai-key
```

Requires Codex CLI in the minion image. The provider runs `codex exec` and
exports `OPENAI_API_KEY`.

### Kimi

```yaml
agent:
  provider_class: user_data.agent_providers.kimi.KimiAgentProvider
  kimi_api_key: sk-your-kimi-key
```

Requires Kimi Code CLI in the minion image. The minion image installs the npm
package `@moonshot-ai/kimi-code` using the `KIMI_CODE_VERSION` build argument.

The provider uses the checked-in template at
`user_data/kimi_code_home/config.toml`, replaces `${KIMI_API_KEY}` with
`agent.kimi_api_key` from the active config file or the `KIMI_API_KEY`
environment variable, and writes the final file to Kimi's default home:

```text
~/.kimi-code/config.toml
```

In the Fly minion image, that path is:

```text
/root/.kimi-code/config.toml
```

The provider then runs Kimi without an explicit model flag so the model comes
from the TOML `default_model` value:

```bash
kimi --prompt "<prompt>"
```

When resuming a shared session, the provider uses:

```bash
kimi --session <session_id> --prompt "<prompt>"
```

The default Kimi TOML currently uses Moonshot's OpenAI-compatible endpoint and
the `kimi-k2.7-code` model:

```toml
default_model = "kimi-k2.7-code"
default_permission_mode = "yolo"

[providers.moonshot]
type = "openai"
base_url = "https://api.moonshot.ai/v1"
api_key = "${KIMI_API_KEY}"

[models."kimi-k2.7-code"]
provider = "moonshot"
model = "kimi-k2.7-code"
max_context_size = 131072
```

## Creating A New Agent Provider

Agent providers live in `user_data/agent_providers/`.

Create a new file, for example `user_data/agent_providers/acme.py`:

```python
"""Acme CLI agent provider."""

from __future__ import annotations

import logging

from minions_army.core.runtime.logging import format_command, log_event
from minions_army.infrastructure.agents.base import AgentExecutionContext, AgentProvider

logger = logging.getLogger("minions_army.agent_providers.acme")


class AcmeAgentProvider(AgentProvider):
    name = "acme"
    model = "acme-fast"
    reasoning_effort = "low"
    allowed_tools = "Bash,Read,Edit,Write,Glob,Grep"
    api_key_config_name = "acme_api_key"
    api_key_environment_variable = "ACME_API_KEY"

    def setup_tool_name(self) -> str:
        return self.name

    def supports_shared_session(self) -> bool:
        return False

    def run(self, context: AgentExecutionContext) -> str:
        command = [
            "acme",
            "run",
            "--model",
            self.model,
            "--prompt",
            context.prompt,
        ]
        log_event(
            logger,
            logging.INFO,
            "agent.stage.command.start",
            stage_name=context.stage_name,
            engine=self.name,
            command=format_command(command),
            cwd=context.cwd,
            model=self.model,
        )
        completed = context.run_subprocess(
            command,
            step=f"agent:{context.stage_name}",
            cwd=context.cwd,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise SystemExit(completed.returncode)
        return completed.stdout
```

Then select it in config:

```yaml
agent:
  provider_class: user_data.agent_providers.acme.AcmeAgentProvider
  acme_api_key: acme-your-key
```

Provider rules:

- Keep provider-specific CLI details inside the provider.
- Do not add provider-specific environment logic to launchers or core runtime.
- Set `api_key_config_name` to the provider-specific key name.
- Set `api_key_environment_variable` when the CLI expects an environment variable.
- Add unit tests for command construction, API key mapping, and failure handling.

## Creating A New Pipeline Provider

Pipeline providers live in `user_data/pipeline_steps/`.

Create a new file, for example `user_data/pipeline_steps/custom.py`:

```python
"""Custom pipeline provider."""

from __future__ import annotations

from minions_army.infrastructure.pipeline_steps.base import PipelineStepsProvider
from minions_army.core.runtime.steps.bootstrap import OpenSpecBootstrapStep
from minions_army.core.runtime.steps.clone_repository import CloneRepositoryStep
from minions_army.core.runtime.steps.checkout_branch import CheckoutBranchStep
from minions_army.core.runtime.steps.configure_git import ConfigureGitStep
from minions_army.core.runtime.steps.verify_build import VerifyBuildStep


class CustomPipelineStepsProvider(PipelineStepsProvider):
    name = "custom"

    def build(self):
        return [
            CloneRepositoryStep(),
            CheckoutBranchStep(),
            ConfigureGitStep(),
            OpenSpecBootstrapStep(),
            VerifyBuildStep(),
        ]
```

Then select it in config:

```yaml
workflow:
  steps_provider_class: user_data.pipeline_steps.custom.CustomPipelineStepsProvider
  constitution_depth: standard
```

Pipeline rules:

- Keep pipeline ordering in the provider.
- Reuse existing step classes where possible.
- Add a new step class only when existing runtime steps cannot express the
  behavior.
- Add unit tests that assert the provider returns the intended ordered steps.

## Image And Deployment Notes

`Dockerfile.minion` copies `user_data/` into the image:

```dockerfile
COPY user_data ./user_data
```

Because of that, changes to `user_data/orchestrator/config.yml`, providers, Kimi's
`user_data/kimi_code_home/config.toml` template, or pipeline files require a
minion image rebuild before Fly Machines or other remote launchers see them.

Docker Compose bind-mounts `user_data/api/config.yml`, so local compose runs pick up
API config changes without rebuilding the image. The minion's config is baked into
the image, so changes there still need `docker compose build`.

## Troubleshooting

### `database.url is required`

Your minion config probably contains an empty `database.url` or an old env
placeholder. Set a concrete database URL in `user_data/orchestrator/config.yml` and
rebuild the minion image.

### Provider says an agent key is required

The selected provider requires the key named by its `api_key_config_name`, such
as `agent.anthropic_api_key`, `agent.openai_api_key`, or
`agent.kimi_api_key`.

For Kimi, set either:

```yaml
agent:
  kimi_api_key: sk-your-kimi-key
```

or:

```yaml
agent:
  kimi_api_key: ${KIMI_API_KEY}
```

When using the placeholder form, the minion process must receive a real
`KIMI_API_KEY` environment variable.

### Kimi says `LLM not set`

This means Kimi started but did not find a usable LLM configuration. Check the
Kimi provider logs for:

- `config_path`, usually `/root/.kimi-code/config.toml` in Fly
- `config_exists=True`
- `config_has_placeholder=False`
- `config_has_api_key_entry=True`
- `has_configured_api_key=True`
- `event=agent.kimi.version`

If `config_has_placeholder=True`, `${KIMI_API_KEY}` was not replaced before
Kimi started. Set `agent.kimi_api_key` to a concrete value or provide the
`KIMI_API_KEY` environment variable to the minion.

If the logs show `agent.kimi.executable_missing`, the minion image does not
have the `kimi` executable in `PATH`. Rebuild the minion image after changing
`Dockerfile.minion`.

### Fly launch works but deploy fails

Check:

- `deploy.mode: flyctl`
- `launcher.fly_app`
- `launcher.fly_api_token`

The deploy step reads these from config and passes `FLY_API_TOKEN` only to the
`flyctl deploy` subprocess.

### Slack progress messages do not appear

Check:

- `slack.bot_token`
- The incoming Slack payload includes channel/thread information.
- The minion environment includes dynamic Slack context from the launcher.
