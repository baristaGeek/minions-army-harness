# Use Cases

This document describes the current behavior of Minions Army and the product boundaries for future work.

## Overview

Minions Army receives task requests through an API, persists the request, and delegates execution to a detached minion container. The current implementation focuses on Slack-style text messages and configurable spec-driven development execution through Spec Kit or OpenSpec.

## UC-001: Receive Slack Message And Start Minion Execution

### Description

Accept a Slack text-message webhook, store the message in PostgreSQL, and start a Docker sibling container using the message text as the minion input.

### Actors

- Slack or a Slack-compatible client.
- Minions Army API.
- PostgreSQL.
- Docker daemon.
- Minion container.
- Codex inside the minion container.

### Preconditions

- The API is running.
- PostgreSQL is reachable.
- Database migrations have been applied.
- The API process can access the Docker daemon when minion execution is required.
- The minion image has been built.
- `repository.name` in `user_data/config.yml` points to a cloneable repository.

### Main Flow

1. A client sends a payload to `POST /api/v1/webhooks/slack/messages`.
2. The API validates that the payload contains a channel and text.
3. If `SLACK_ALLOWED_CHANNEL_ID` is configured, the API rejects messages from other channels.
4. The application service creates a `SlackMessage` domain model.
5. The repository persists the message in the `slack_messages` table.
6. The API returns `202 Accepted`.
7. A background task starts a detached Docker minion container.
8. The minion receives the original message as `MINION_INPUT_MESSAGE`.
9. The minion clones the configured repository and creates a task branch.
10. The minion orchestrator runs the specification, planner, tasks, and implementation agents in order inside the cloned repository using the selected SDD framework.
11. Codex runs the rendered prompt.
12. After the final implementation commit is pushed, Codex creates a pull request for the task branch with a title and description based on the completed work.

### Alternative Flows

- Slack URL verification payloads return the received challenge.
- Invalid payloads return validation errors.
- Messages from disallowed channels are rejected when `SLACK_ALLOWED_CHANNEL_ID` is set.
- Docker startup failures are logged and do not change an already accepted webhook response.
- If `MINION_INPUT_MESSAGE` is missing inside the minion, the entrypoint exits with a configuration error.
- If the configured prompt template is missing inside the minion image, the entrypoint exits with a prompt-template error.
- If pull request creation fails because credentials, permissions, or platform tooling are unavailable, the minion reports the failure and leaves the pushed task branch available.

### Postconditions

- The accepted Slack message is persisted.
- A minion container start has been attempted.
- The API request does not wait for Codex execution to finish.

### Business Rules

- Slack signature validation is out of scope for the current MVP.
- Authentication and authorization are out of scope for the current MVP.
- The API should return quickly and delegate long-running work.
- The minion prompts are versioned with the repository under `execution/prompts/`.
- The selected SDD framework is configured with `MINION_SPEC_FRAMEWORK` and passed to the minion as `SPEC_FRAMEWORK`.
- Pull request title and description should be generated from the completed work, not from a fixed template.

## UC-002: Slack URL Verification

### Description

Respond to Slack URL verification requests so Slack-compatible integrations can validate the webhook endpoint.

### Main Flow

1. Slack sends a verification payload containing a challenge.
2. The API recognizes the challenge.
3. The API returns the challenge in the response.

### Postconditions

- No minion execution is started for URL verification.
- No task branch is created.

## Planned Use Cases

The following use cases are intentionally not implemented yet:

- Policy generation from engineering constitutions and language profiles.
- Constitution merging.
- Prompt generation from reusable policy components.
- Language or stack detection.
- Worker queues or message brokers.
- AI provider abstraction.
- GitHub pull request automation outside the minion prompt.
- Authentication and authorization.

## Documentation Rules

- Add a use case before implementing a significant new behavior.
- Keep actors, preconditions, main flow, alternatives, and postconditions current.
- Update this document when endpoint behavior, execution behavior, or configuration changes.
