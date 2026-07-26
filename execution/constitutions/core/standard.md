---
name: Standard
level: 2
description: Team-ready engineering expectations that extend the Basic constitution.
---

# Standard Engineering Constitution

This constitution includes all Basic expectations and adds the following standards.

## Maintainability

- Modules must have clear ownership of responsibilities.
- Shared behavior should be centralized when duplication creates maintenance risk.
- Public contracts must remain stable unless the change explicitly requires a contract revision.
- Implementation details should not leak across boundaries.

## Dependency Management

- Dependencies must have a clear purpose and be justified by value over maintenance cost.
- New dependencies should minimize coupling and avoid replacing simple native capabilities.
- Dependency usage must be isolated enough that future replacement remains practical.

## Testing

- Tests should cover successful behavior, relevant edge cases, and expected failure cases.
- Test fixtures must be explicit and local to the behavior under test where possible.
- Tests should fail for meaningful behavioral regressions, not incidental implementation changes.

## Logging

- Important state transitions and failures should be observable.
- Logs must avoid sensitive data.
- Log messages should be actionable and concise.

## Security

- Inputs must be validated at trust boundaries.
- Sensitive values must not be exposed through logs, errors, or documentation.
- Access to protected behavior must be intentional and auditable.

## Code Reviews

- Changes should be reviewable in focused units.
- Review should consider correctness, maintainability, test coverage, security, and operational impact.
- Review feedback must be resolved deliberately before completion.

## Safety and Guardrails

- Never perform destructive data operations. No `DROP TABLE`/`DROP DATABASE`/`TRUNCATE`, no
  unconditional `DELETE`, no dropping columns or tables that hold data.
- Only additive, reversible schema migrations. Never run `prisma migrate reset`,
  `prisma db push --force-reset`, or any command that resets or wipes a database.
- Keep the code very simple: prefer the smallest change that satisfies the request. Avoid new
  abstractions, dependencies, or scope beyond what was asked.
- If the application cannot build or render, do not open or approve a pull request.
- Never commit secrets, credentials, or tokens.

## Definition of Done

- All Basic and Standard expectations are satisfied.
- Automated checks relevant to the changed area pass.
- Documentation and tests reflect the final behavior.
- No destructive operations were introduced and the application still builds/renders.
