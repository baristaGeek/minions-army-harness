# Minions Army Harness

A small, Slack-first agent harness for **responsible vibe-coding**. 

Send it a plain-English request ("add a dark theme to the app", "add a merchant column to the recent transactions table") and it turns that into a spec, writes the code in an isolated sandbox, opens a pull request, reviews it adversarially, and — if you let it — deploys. No one has to learn a CLI or touch a coding agent directly. It's a miniature, self-hostable take on the "fleet of coding minions" idea.

## Getting started

### Tier 1 — run it locally

You need an **Anthropic API key** and a **GitHub token** for a repo you own (fork this one — the
minion works against the bundled [`sample-app/`](sample-app/)).

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...
export REPOSITORY_NAME=your-username/minions-army-harness   # a repo your token can push to

docker compose up --build            # boots the API, Postgres, and builds the minion image

# In another shell, fire a request at the webhook:
curl -X POST http://localhost:8000/api/v1/webhooks/slack/me
  -H "Content-Type: application/json" \
  -d '{"channel":"C123","user":"U123","text":"add a footer .1"}'
```

A minion spins up as a local Docker sibling container, runs OpenSpec against your fork, gates on
`npm run build`, and **opens a real pull request**. Review ult, so the demo
stops at the PR. It costs real LLM tokens per run and needs a repo you don't mind a bot committing to.

Config lives in `user_data/api/config.yml` (read by the API) and `user_data/orchestrator/config.yml`
(read inside the minion).

### Tier 2 — run it in the cloud

Two Fly apps: the API (`fly.toml`) and one that owns the miphemeral
machines (`fly.minion.toml`).

```bash
fly apps create minions-army
fly apps create minions-army-minion

# 1. Build and push the minion image. --image-label must match launcher.image below.
fly deploy --config fly.minion.toml --remote-only --build-oatest

# 2. Edit user_data/api/config.yml — baked into the API imaoy:
#    launcher:
#      backend: fly_machines
#      image: registry.fly.io/minions-army-minion:latest
#      fly_machine_app: minions-army-minion   # hosts the e
#      fly_app: <the app you deploy>          # required when deploy.mode is flyctl
#      fly_api_token: ${FLY_API_TOKEN}        # no env fall
#    repository.name + verification.command/cwd -> your repo
#    reviewer.enabled: true
#    deploy.mode: flyctl
#    slack.allowed_channel_id: <channel the bot listens to>

# 3. Secrets fill the ${VAR} placeholders.
fly secrets set --app minions-army \
  DATABASE_URL=postgres://...  ANTHROPIC_API_KEY=sk-ant-...
  SLACK_BOT_TOKEN=xoxb-...  FLY_API_TOKEN=$(fly tokens create deploy)

# 4. Deploy, then migrate (fly.toml has no release_command).
fly deploy --config fly.toml --remote-only
fly ssh console --app minions-army -C "alembic upgrade head"
```

Then create a Slack app: point **Event Subscriptions** at
`https://minions-army.fly.dev/api/v1/webhooks/slack/messages` (the endpoint echoes Slack's
`challenge`), subscribe to `app_mention`, and give the bot ly in-thread.
There is no signing-secret check, so `slack.allowed_channel_id` is the gate.

Every message now gets its own ephemeral Fly Machine, created on receipt and destroyed on exit.

## Configuration

One YAML file per process, with `${VAR}` placeholders filled from the environment at load time. Both
ship working defaults; to start from scratch, `cp config_exta/api/config.yml`
(that path is the one the loader reads — override with `MINIONS_CONFIG_PATH`). Key knobs:

| Field | What it controls |
|-------|------------------|
| `agent.provider_class` | `claude` / `codex` / `kimi`, or the `fallback` chain across all three (the default) |
| `launcher.backend` | `docker` (local sibling container) ol Fly VM) |
| `reviewer.enabled` | Adversarial review + auto-merge/deploy gate (**off by default**) |
| `reviewer.engine` | `claude_cli` (default), `agent` (inheor `dspy` |
| `deploy.mode` | `none` (default), `flyctl`, or `github_actions` (delegates — you supply the workflow) |

## Development

```bash
pip install -r requirements-dev.txt
ruff check minions_army tests
mypy minions_army
pytest
```

## How it works

1. **A message comes in** — via the Slack webhook (or the generic Web API endpoint).
2. **A minion is spawned** in an isolated sandbox: a **local Docker sibling container** (Tier 1) or an
   **ephemeral Fly Machine** (Tier 2) that is destroyed when the run ends.
3. **The agent runs [OpenSpec](https://github.com/Fission-AI/OpenSpec)** — a lightweight
   spec-driven-development flow — to disambiguate the request into a concrete spec, then implement it.
   Providers fall back **Claude → Codex → Kimi**, so one outage or empty credit balance doesn't stop the run.
4. **A PR is opened, then reviewed adversarially.** LLMs are sycophantic and poor at judging their own
   work, so a separate reviewer agent grades the PR. Both writer and reviewer share an
   [engineering constitution](CONSTITUTION.md) that forbids destructive operations (no `DROP TABLE`,
   no unconditional `DELETE`, additive-and-reversible migrations only).
5. **Ship or flag.** With the reviewer enabled, an approved PR can auto-merge and deploy; otherwise the
   PR is left for a human. (Both are **off by default** — the demo just opens a PR.)



See [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a PR.

## License

[MIT](LICENSE).
