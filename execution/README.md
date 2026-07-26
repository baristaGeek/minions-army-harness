# Execution Assets

This folder contains source material used to guide technical execution.

Execution assets are intentionally separate from runtime source code. Files here may be copied into containers, consumed by future builders, or used as source material for workflows, but they should not import application code or depend on API, database, Docker, worker, messaging, or AI-provider implementations.

## Structure

```text
execution/
  README.md
  prompts/
    README.md
    agents/
      specification_agent/
        prompt.md
      planner_agent/
        prompt.md
      tasks_agent/
        prompt.md
      implementation_agent/
        prompt.md
    expected-response-format.md
    agent-tools.md
  constitutions/
    README.md
    core/
      basic.md
      standard.md
      professional.md
      enterprise.md
    profiles/
      README.md
      tools/
        agent-tools.md
      angular.yaml
      dotnet.yaml
      golang.yaml
      javascript.yaml
      nodejs.yaml
      python.yaml
      react.yaml
```

## Prompts

`execution/prompts/` contains reusable prompt templates and fragments.

See [Prompts](prompts/README.md) for the prompt structure and workflow pieces.

## Constitutions

`execution/constitutions/` contains reusable engineering standards and profiles.

See [Constitutions](constitutions/README.md) for the constitution structure and profiles.

## Responsibilities

Execution assets may define:

- Prompt templates.
- Engineering standards.
- Technology profile metadata.
- Reusable source material for future execution policies.

Execution assets must not define:

- API routes.
- Runtime services.
- Worker orchestration.
- Docker execution logic.
- AI provider integrations.
- Policy generation logic.
- Prompt generation logic.

## Adding Assets

When adding a prompt:

- Place it under `execution/prompts/`.
- Use a descriptive file name.
- Document required placeholders.
- Update Docker or entrypoint paths if the prompt is used by a container image.

When adding a constitution-driven agent prompt:

- Place it under `execution/prompts/<framework>/constitution/`.
- Read the root-level `CONSTITUTION.md` file as the input contract for the stage.
- Keep the prompt focused on preparing or consuming the constitution, not on application implementation.

When adding constitution material:

- Place constitution files directly under `execution/constitutions/core/`.
- Place tool profiles under `execution/constitutions/profiles/tools/`.
- Place stack profiles directly under `execution/constitutions/profiles/`.
- Keep constitution assets independent from runtime implementation details.
