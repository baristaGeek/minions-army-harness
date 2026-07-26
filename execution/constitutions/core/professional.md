---
name: Professional
level: 3
description: Production-grade engineering expectations that extend the Standard constitution.
---

# Professional Engineering Constitution

This constitution includes all Basic and Standard expectations and adds the following standards.

## Architecture

- Boundaries must be explicit and aligned with business responsibilities.
- High-level policy must not depend on low-level implementation details.
- Components should communicate through stable contracts.
- Designs should allow future extension without modifying unrelated existing behavior.

## Reliability

- Expected failure modes must be understood and handled consistently.
- Recovery behavior should be predictable.
- Critical operations should avoid partial completion without a clear remediation path.
- State changes should be safe to retry where practical.

## Performance

- Performance-sensitive paths must avoid unnecessary work.
- Resource usage should be proportional to the task.
- Changes that may affect latency, throughput, or resource consumption should be evaluated before completion.

## Observability

- The system should expose enough information to diagnose production issues.
- Errors should be traceable across meaningful execution boundaries.
- Metrics, logs, and diagnostics should support incident analysis without exposing sensitive data.

## Testing

- Tests should cover architectural boundaries and integration contracts where risk justifies it.
- Regression tests should be added for defects that reach completed work.
- Test suites should remain fast enough to support frequent execution.

## Documentation

- Architectural decisions should be recorded when they constrain future work.
- Public contracts, invariants, and failure behavior should be documented.
- Documentation must distinguish requirements from implementation choices.

## Definition of Done

- All Basic, Standard, and Professional expectations are satisfied.
- Risk has been assessed for reliability, performance, security, and maintainability.
- The change is ready for production use within its intended scope.

## Safety and Guardrails

- Never perform destructive data operations. No `DROP TABLE`/`DROP DATABASE`/`TRUNCATE`, no
  unconditional `DELETE`, no dropping columns or tables that hold data.
- Only additive, reversible schema migrations. Never run `prisma migrate reset`,
  `prisma db push --force-reset`, or any command that resets or wipes a database.
- Keep the code very simple: prefer the smallest change that satisfies the request.
- If the application cannot build or render, do not open or approve a pull request.
- Never commit secrets, credentials, or tokens.
