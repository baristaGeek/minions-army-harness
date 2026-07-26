# Development Guide

This guide describes the recommended local workflow for developing Minions Army.

## Prerequisites

- Python 3.13 or newer.
- Docker and Docker Compose.
- Git.
- PostgreSQL, either local or through Docker Compose.

## Repository Setup

```bash
git clone <repository-url>
cd minions-army
```

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

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

Edit the runtime YAML config. The API reads `user_data/api/config.yml`; the minion reads
`user_data/orchestrator/config.yml`. Both are checked in. To start from the example instead:

```bash
cp user_data/config.example.yml user_data/api/config.yml
```

On Windows PowerShell:

```powershell
Copy-Item user_data\config.example.yml user_data\api\config.yml
```

Review `user_data/api/config.yml` before running the application.

## Database

Start PostgreSQL with Docker Compose:

```bash
docker-compose up -d db
```

Apply migrations:

```bash
alembic upgrade head
```

Create a new migration after changing SQLAlchemy models:

```bash
alembic revision --autogenerate -m "describe change"
```

Review generated migration files before committing them.

## Run The API

```bash
uvicorn minions_army.infrastructure.api.fastapi_app:app --reload
```

Or use the Makefile shortcut:

```bash
make dev
```

The API is available at `http://localhost:8000`.

## Docker Development

Build the API and minion images:

```bash
docker-compose build
```

Start all services:

```bash
docker-compose up -d
```

View API logs:

```bash
docker-compose logs -f api
```

Stop services:

```bash
docker-compose down
```

## Fly Deploys

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

## Minion Prompt Path

The minion image depends on the prompt bundle at:

```text
execution/prompts/minions/
```

The Dockerfile copies it into:

```text
/opt/minions-army/execution/prompts/minions/
```

If this path changes, update:

- `Dockerfile.minion`
- `minions_army/cli/commands/run.py`
- `QUICKSTART.md`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/USER_CASES.md`

## Tests

Run all tests:

```bash
pytest
```

Run unit tests:

```bash
pytest tests/unit
```

Run integration tests:

```bash
pytest tests/integration
```

Run coverage:

```bash
pytest --cov=minions_army --cov-report=term-missing
```

## Quality Checks

```bash
black minions_army tests
ruff check minions_army tests
mypy minions_army
```

Makefile shortcuts:

```bash
make format
make lint
make type-check
make check
```

## IDE Guidance

Recommended VS Code extensions:

- Python.
- Pylance.
- Black Formatter.
- Ruff.
- pytest support.

For any IDE:

- Use `.venv` as the Python interpreter.
- Use pytest as the test runner.
- Enable format-on-save only if it uses Black.
- Keep runtime configuration aligned with `user_data/config.example.yml`.

## Troubleshooting

If port `8000` is already in use:

```bash
lsof -i :8000
kill -9 <PID>
```

On Windows:

```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

If database connection fails:

- Confirm PostgreSQL is running.
- Confirm `database.url` in `user_data/api/config.yml`.
- Apply migrations with `alembic upgrade head`.

If Docker minion execution fails:

- Rebuild images with `docker-compose build`.
- Confirm `launcher.image`.
- Confirm `repository.name`.
- Inspect the minion logs with `docker logs <minion_container_name>`.
- Set `MINION_TESTING_MODE=true` to keep containers alive for inspection.

## Related Documentation

- [Quick Start](../QUICKSTART.md)
- [Architecture](ARCHITECTURE.md)
- [Use Cases](USER_CASES.md)
- [Project Constitution](../CONSTITUTION.md)
- [Execution Assets](../execution/README.md)
