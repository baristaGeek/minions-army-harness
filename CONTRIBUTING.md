# Contributing To Minions Army

Thank you for contributing. This guide explains how to make changes safely and consistently.

## Before You Start

1. Read [README.md](README.md) for project context.
2. Read [QUICKSTART.md](QUICKSTART.md) for setup instructions.
3. Read [CONSTITUTION.md](CONSTITUTION.md) for engineering rules.
4. Review [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before changing layer boundaries.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
alembic upgrade head
```

## Workflow

1. Create a focused branch.
2. Make a small, reviewable change.
3. Add or update tests when behavior changes.
4. Update documentation when setup, runtime behavior, configuration, API behavior, or execution asset paths change.
5. Run quality checks.
6. Open a pull request with a clear description.

## Quality Checks

Run these before submitting work:

```bash
black minions_army tests
ruff check minions_army tests
mypy minions_army
pytest
```

For coverage:

```bash
pytest --cov=minions_army --cov-report=term-missing
```

Makefile shortcuts are also available:

```bash
make format
make lint
make type-check
make test
make coverage
```

## Architecture Rules

- Keep domain code independent from FastAPI, SQLAlchemy, Docker, and settings.
- Keep route handlers thin.
- Put orchestration in the application layer.
- Put external integrations in infrastructure.
- Keep execution assets under `execution/`.
- Avoid unrelated refactors in feature branches.

## Testing Rules

- Write tests for new behavior.
- Keep unit tests deterministic.
- Mock external services in unit tests.
- Add integration tests when behavior crosses important runtime boundaries.
- Use descriptive test names that explain the expected behavior.

Example:

```python
def test_accept_message_persists_payload_and_returns_message_id():
    """Accepted messages are persisted and exposed through the response."""
```

## Documentation Rules

Update documentation when changing:

- API endpoints.
- Environment variables.
- Docker behavior.
- Minion execution.
- Database migrations.
- Execution asset paths.
- Project structure.
- Architecture decisions.

Use English for all repository documentation.

## Commit Guidelines

- Use clear, descriptive commit messages.
- Keep commits focused on one logical change.
- Reference related issues when applicable.

Example:

```text
feat: add Slack channel allow-list validation
```

## Pull Request Checklist

- The change is focused.
- Tests pass.
- Formatting passes.
- Linting passes.
- Type checking passes.
- Documentation is updated.
- Docker or minion paths still work when touched.

## Reporting Issues

When reporting a bug, include:

- A clear title.
- Steps to reproduce.
- Expected behavior.
- Actual behavior.
- Relevant logs.
- Python version, operating system, and Docker version when relevant.

## Conduct

Be respectful, direct, and constructive. Keep reviews focused on correctness, maintainability, reliability, security, and clarity.
