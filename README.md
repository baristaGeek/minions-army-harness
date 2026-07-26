# Minions Army Harness

A small, Slack-first agent harness for **responsible vibe-coding**. Send it a plain-English request
("add a dark theme to the app", "add a merchant column to the recent transactions table") and it turns
that into a spec, writes the code in an isolated sandbox, opens a pull request, reviews it
adversarially, and — if you let it — deploys. No one has to learn a CLI or touch a coding agent
directly.

It's a miniature, self-hostable take on the "fleet of coding minions" idea, built around Clean
Architecture (FastAPI API, application services, domain models, pluggable infrastructure).

## Getting started

There are three tiers — go as deep as you want.

### Tier 1 — local demo (~10 min, no Fly, no Slack)
You need only two things: an **Anthropic API key** and a **GitHub token** for a repo you own (fork this
one — the minion works against the bundled [`sample-app/`](sample-app/)).

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...
export REPOSITORY_NAME=your-username/minions-army-harness   # a repo your token can push to

docker compose up --build            # boots the API, Postgres, and builds the minion image

# In another shell, fire a request at the webhook:
curl -X POST http://localhost:8000/api/v1/webhooks/slack/messages \
  -H "Content-Type: application/json" \
  -d '{"channel":"C123","user":"U123","text":"add a footer to the sample app","ts":"1.1"}'
```

A minion spins up as a local Docker sibling container, runs OpenSpec against your fork, and **opens a
real pull request**. That's the "it actually works" moment — zero cloud infra beyond one API key and one
token. It costs real LLM tokens per run and needs a repo you don't mind a bot committing to.

Config for this path lives in [`user_data/api/config.yml`](user_data/api/config.yml) (read by the API)
and [`user_data/orchestrator/config.yml`](user_data/orchestrator/config.yml) (read inside the minion).

### Tier 2 — run it for real
Switch `launcher.backend` to `fly_machines`, create a Fly app + Slack app, set the secrets, enable the
reviewer, and point it at your own repo. See [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) and
[`QUICKSTART.md`](QUICKSTART.md). This is the production path — the appendix, not the hero.

## Configuration

Everything is driven by one YAML file (env vars fill `${VAR}` placeholders at load time). Start from
[`config_examples/minimal.yml`](config_examples/minimal.yml) or the provider examples under
`config_examples/`. Key knobs:

| Field | What it controls |
|-------|------------------|
| `agent.provider_class` | `claude` / `codex` / `kimi`, or the `fallback` chain across all three |
| `launcher.backend` | `docker` (local sibling) or `fly_machines` (ephemeral Fly VM) |
| `reviewer.enabled` | Adversarial review + auto-merge/deploy gate (off by default) |
| `deploy.mode` | `none` / `github_actions` / `flyctl` |

```

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
