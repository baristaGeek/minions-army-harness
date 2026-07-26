---
name: Basic
level: 1
description: Foundational engineering expectations for small, low-risk changes.
---

# Basic Engineering Constitution

## Code Quality

- Code must be understandable, purposeful, and limited to the requested behavior.
- Names must communicate intent clearly.
- Unused code, dead branches, and speculative abstractions must be avoided.
- Changes must preserve existing behavior unless a behavior change is explicitly required.

## Simplicity

- Prefer the simplest design that satisfies the current requirement.
- Avoid adding layers, indirection, or configuration without a clear present need.
- Keep responsibilities small and easy to reason about.

## Readability

- Code should be organized so a maintainer can follow the main path quickly.
- Complex logic should be decomposed into clear units.
- Comments should explain intent or non-obvious decisions, not restate the code.

## Testing

- New behavior must be covered by deterministic tests.
- Tests should verify externally observable behavior.
- Tests must avoid dependence on time, ordering, or external services unless controlled by the test.

## Error Handling

- Invalid inputs and expected failure cases must be handled deliberately.
- Errors should preserve enough context for diagnosis.
- Failure handling must not hide defects silently.

## Documentation

- Public behavior and operational assumptions should be documented where future maintainers will find them.
- Documentation must be updated when the change alters behavior, configuration, or usage.

## Definition of Done

- The change satisfies the requested behavior.
- Relevant tests pass.
- The implementation is readable, maintainable, and free of known avoidable defects.

## Safety and Guardrails

- Never perform destructive data operations. No `DROP TABLE`/`DROP DATABASE`/`TRUNCATE`, no
  unconditional `DELETE`, no dropping columns or tables that hold data.
- Only additive, reversible schema migrations. Never run `prisma migrate reset`,
  `prisma db push --force-reset`, or any command that resets or wipes a database.
- Keep the code very simple: prefer the smallest change that satisfies the request.
- If the application cannot build or render, do not open or approve a pull request.
- Never commit secrets, credentials, or tokens.
