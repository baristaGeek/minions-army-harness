# Alembic Migrations

This folder contains database migration configuration for SQLAlchemy and Alembic.

## Structure

- `env.py`: Alembic runtime configuration.
- `script.py.mako`: migration file template.
- `versions/`: migration revisions.

## Apply Migrations

```bash
alembic upgrade head
```

With Docker Compose:

```bash
docker-compose exec api alembic upgrade head
```

## Create A Migration

```bash
alembic revision --autogenerate -m "describe change"
```

Always review generated migrations before committing them.

## Common Commands

```bash
alembic current
alembic history
alembic upgrade +1
alembic downgrade -1
```

## Rules

- Keep migrations small and focused.
- Use descriptive migration messages.
- Test upgrade and downgrade paths when practical.
- Do not edit migrations that have already been applied in shared environments.
- Create a new migration to correct a released schema change.
