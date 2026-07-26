# Architecture

Minions Army follows Clean Architecture. The application keeps domain rules independent from HTTP, Docker, database persistence, and other infrastructure concerns.

## Goals

- Keep business behavior easy to test.
- Keep external integrations replaceable.
- Make runtime flow explicit.
- Avoid coupling execution assets to application code.
- Support future policy or agent orchestration without reshaping the core service.

## Layers

```text
API
  -> Application
      -> Domain
          <- Infrastructure implementations
```

Dependencies should point inward. Outer layers may know about inner layers, but inner layers should not depend on outer layers.

## API Layer

Location: `minions_army/infrastructure/api/`

Responsibilities:

- Define FastAPI routes.
- Validate HTTP requests and responses with Pydantic schemas.
- Convert HTTP concepts into application calls.
- Return appropriate HTTP status codes.
- Keep controllers thin.

Important files:

- `routes.py`: versioned API routes and webhook endpoints.
- `schemas.py`: request and response models.
- `dependencies.py`: dependency wiring for route handlers.
- `middleware.py`: HTTP middleware.

## Application Layer

Location: `minions_army/application/`

Responsibilities:

- Implement use cases.
- Orchestrate domain models and infrastructure interfaces.
- Keep process flow readable.
- Avoid direct HTTP or database concerns.

The Slack webhook service accepts validated payloads, creates a domain message, persists it through a repository, and delegates long-running work to a task runner.

## Domain Layer

Location: `minions_army/domain/`

Responsibilities:

- Define domain models.
- Define repository contracts.
- Define domain exceptions.
- Stay framework-independent where practical.

The domain layer should not import FastAPI, SQLAlchemy, Docker clients, or application settings.

## Infrastructure Layer

Location: `minions_army/infrastructure/`

Responsibilities:

- Load configuration.
- Manage database access.
- Implement persistence repositories.
- Start Docker sibling containers.
- Configure logging.

Infrastructure code is allowed to depend on external libraries and operating-system resources because it is the boundary between the application and the outside world.

## Execution Assets

Location: `execution/`

Execution assets are source material used by minion workflows and future policy-generation components.

- `execution/prompts/`: prompt templates used by minion execution.
- `execution/constitutions/`: engineering rules and language profiles.

These files are intentionally outside the Python runtime package because they are not importable application modules. Application code may reference their paths when needed, but the assets themselves should remain independent from API, Docker, database, and worker implementations.

## Runtime Flow

```text
Slack or client
  -> POST /api/v1/webhooks/slack/messages
  -> API schema validation
  -> Slack webhook application service
  -> SlackMessage domain model
  -> Repository persistence
  -> 202 Accepted response
  -> Background task starts Docker sibling container
  -> Minion orchestrator clones target repository
  -> Minion runs specification, planner, tasks, and implementation agents
  -> Codex pushes the final task branch state and creates a pull request
```

The HTTP request does not wait for the minion workload to finish. Docker startup failures are logged separately from the accepted webhook response.

## Database

The service uses SQLAlchemy models for persistence and Alembic for migrations.

Rules:

- Keep ORM models in infrastructure.
- Keep domain models separate from ORM models.
- Use migrations for schema changes.
- Review generated migrations before applying them.

## Configuration

Configuration is loaded through the typed YAML schema in `minions_army/core/config/schema.py`. Two
processes read two different files:

- The **API** defaults to `user_data/api/config.yml` (`DEFAULT_USER_CONFIG` in
  `minions_army/core/config/defaults.py`).
- The **minion** reads `user_data/orchestrator/config.yml`, set as `MINIONS_CONFIG_PATH` in
  `Dockerfile.minion`.

Either can be overridden with the `MINIONS_CONFIG_PATH` environment variable, or with `--config` on
the `minion-orchestrator` entrypoint.

Common sections:

- `database`
- `slack`
- `repository`
- `agent`
- `workflow`
- `launcher`
- `verification`
- `reviewer`
- `deploy`

Secrets can be configured as concrete values in the active config file or through
explicit YAML placeholders. For remote minion images, concrete values are simpler
because `user_data/` is copied into the image. Providers and runtime
adapters translate configured values to CLI environment variables only at
subprocess boundaries.

## Minion Execution via Docker

The API container can start minion workloads through the configured launcher. The minion receives dynamic event data through environment variables:

- `MINION_INPUT_MESSAGE`
- `SLACK_CHANNEL_ID`
- `SLACK_MESSAGE_ID`

The minion image copies `execution/prompts/` and `execution/constitutions/` into `/opt/minions-army/execution/`. The Python orchestrator coordinates the specialized Codex prompts in sequence before handing off the final implementation stage to the existing GitHub workflow. The selected spec-driven-development framework can be `speckit` or `openspec`, and the orchestrator injects the corresponding stage command into the prompt. Before the framework-specific agent runs, the orchestrator copies the selected constitution template into the cloned repository root as `CONSTITUTION.md`.

The minion image includes GitHub CLI, and the orchestrator exposes `GITHUB_TOKEN` as `GH_TOKEN` when a token is provided.

## Minion Execution Backend

The backend used to start the minion workload is selected through global configuration. Docker remains the default path and preserves the current sibling-container behavior. Cloud Jobs Run is an alternate launcher that uses the same minion image and the same environment contract.

Backend-specific launch code lives in infrastructure so the webhook and application layers do not need to know whether Docker or Cloud Jobs Run started the workload.

## Testing Strategy

- Unit tests cover application behavior, domain models, infrastructure adapters, and API route behavior where practical.
- Integration tests cover the API working through configured dependencies.
- Tests should be deterministic and avoid real external services unless the test explicitly targets integration behavior.
- Coverage should remain at or above the repository threshold.

## Error Handling

- Domain errors should carry enough context to diagnose the problem.
- API handlers should return clear HTTP responses for invalid input.
- Infrastructure failures should be logged with actionable context.
- Long-running minion failures should not block the initial webhook response after the message has been accepted.

## Versioning

Public API routes are versioned under `/api/v1`.

Current public routes:

- `GET /health`
- `GET /api/v1/`
- `POST /api/v1/webhooks/slack/messages`
