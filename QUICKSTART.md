# Quick Start

This guide explains how to run Minions Army locally, run it with Docker Compose, execute database migrations, and trigger a minion workflow.

## Prerequisites

- Python 3.13 or newer.
- Docker and Docker Compose.
- Access to a PostgreSQL database, or the PostgreSQL service provided by `docker-compose.yml`.
- A configured Codex environment if you want minion containers to run Codex successfully.

## Runtime Config

Create or edit the runtime YAML config before running the application:

```bash
cp user_data/config.example.yml user_data/config.yml
```

On Windows PowerShell:

```powershell
Copy-Item user_data\config.example.yml user_data\config.yml
```

Important settings are grouped under `database`, `slack`, `repository`, `agent`, `workflow`, `launcher`, `verification`, `reviewer`, and `deploy`.

For remote minion images, prefer concrete values in `user_data/config.yml`
because that file is copied into the image. If you use placeholders, the same
environment variables must exist inside the minion runtime.

```yaml
agent:
  anthropic_api_key: sk-ant-your-anthropic-key
repository:
  github_token: ghp_your_github_token
launcher:
  fly_api_token: fly_your_token
```

See [Configuration Guide](docs/CONFIGURATION.md) for complete provider,
pipeline, and deployment examples.

## Run With Docker Compose

Build the API and minion images:

```bash
docker-compose build
```

Start the services:

```bash
docker-compose up -d
```

Apply database migrations:

```bash
docker-compose exec api alembic upgrade head
```

The API is available at `http://localhost:8000`.

Useful checks:

```bash
curl http://localhost:8000/health
docker-compose ps
docker-compose logs -f api
```

## Run Locally

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements-dev.txt
```

Apply migrations:

```bash
alembic upgrade head
```

Start the API:

```bash
uvicorn minions_army.infrastructure.api.fastapi_app:app --reload
```

The API is available at `http://localhost:8000`.

## Run A Spec-Driven Minion

After the Docker minion image is built, send a feature request through the API. The request field `text` becomes `MINION_INPUT_MESSAGE` in the minion container.

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/slack/messages \
  -H "Content-Type: application/json" \
  -d '{"channel":"C123","user":"U123","text":"Add password reset for users who forgot their password.","ts":"123.456"}'
```

The minion image includes the modular agent prompts under `execution/prompts/` and the constitution templates under `execution/constitutions/`. The `minion-orchestrator` console app coordinates the specialized Codex stages inside the cloned target repository.

The minion image installs both `specify` and `openspec` CLIs globally so the selected framework can bootstrap and run its stages.

The prompt runs the selected SDD framework workflow in this order:

```text
`$speckit-constitution` / `$openspec-constitution`
`$speckit-specify` / `$openspec-specify`
`$speckit-plan` / `$openspec-plan`
`$speckit-tasks` / `$openspec-tasks`
`$speckit-implement` / `$openspec-implement`
```

After each step, the prompt instructs the agent to commit and push the work with a short, precise commit message.

After the implementation is complete and the final commit has been pushed, the prompt instructs the agent to create a pull request with a title and description that match the completed work. The minion image includes GitHub CLI, and `MINION_GITHUB_TOKEN` is passed into the container for GitHub authentication.

Inspect minion containers:

```bash
docker ps -a --filter "name=minion_"
docker logs <minion_container_name>
```

## Deploy To Fly.io

Deploy the main API app with `fly.toml`:

```bash
flyctl deploy --config fly.toml --remote-only
```

Deploy the minion app with `fly.minion.toml`:

```bash
flyctl deploy --config fly.minion.toml --remote-only
```

Build and push the minion image from `Dockerfile.minion` to the Fly registry with the `test` tag, without starting a Machine:

```bash
flyctl deploy --config fly.minion.toml --remote-only --build-only --push --image-label test
```

Update the `minions-army-minion` app to use that pushed image:

```bash
flyctl image update --app minions-army-minion --image registry.fly.io/minions-army-minion:test
```

## API Documentation

When the API is running:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

## Tests And Quality Checks

Run tests:

```bash
pytest
```

Run tests with coverage:

```bash
pytest --cov=minions_army --cov-report=term-missing
```

Run formatting, linting, and type checking:

```bash
black minions_army tests
ruff check minions_army tests
mypy minions_army
```

Run the Makefile shortcuts:

```bash
make format
make lint
make type-check
make test
make coverage
```

## Troubleshooting

If the API cannot connect to the database, verify `database.url` in `user_data/config.yml`, confirm PostgreSQL is running, and apply migrations with `alembic upgrade head`.

If the minion container exits immediately, inspect its logs with `docker logs <minion_container_name>`.

If the minion reports a missing prompt template, rebuild the minion image. The Dockerfile copies the prompt bundle from `execution/prompts/` into `/opt/minions-army/execution/prompts/`.

If Codex authentication is unavailable inside the minion, set `CODEX_HOME` to your host Codex configuration directory so it can be mounted into the container.
