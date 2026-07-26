---
name: Enterprise
level: 4
description: Organization-scale engineering expectations that extend the Professional constitution.
---

# Enterprise Engineering Constitution

This constitution includes all Basic, Standard, and Professional expectations and adds the following standards.

## Governance

- Engineering decisions must be traceable to clear requirements, constraints, or accepted standards.
- Exceptions to standards must be documented with rationale, owner, and review path.
- Ownership of critical components must be clear.

## Compliance

- Data handling must respect applicable policy, retention, and privacy requirements.
- Audit-relevant actions must be attributable and reviewable.
- Controls must be testable and documented.

## Security

- Threats must be considered during design for high-impact changes.
- Privileges should be minimized and reviewed.
- Sensitive operations must include safeguards against misuse, accidental exposure, and unauthorized access.

## Reliability

- Critical behavior must have documented availability and recovery expectations.
- Degraded behavior should be intentional and understandable.
- Operational readiness should be considered before release.

## Change Management

- Changes should be planned to minimize disruption.
- Rollback or remediation paths must be identified for high-risk changes.
- Compatibility impact must be evaluated before public contracts change.

## Maintainability

- Long-lived components must favor clear contracts, strong cohesion, and low coupling.
- Deprecated behavior should have an explicit migration path.
- Knowledge needed to operate or maintain critical behavior must not exist only in individual memory.

## Definition of Done

- All Basic, Standard, Professional, and Enterprise expectations are satisfied.
- Governance, compliance, operational, and security responsibilities are addressed.
- The change is suitable for organization-scale production use.

## Safety and Guardrails

- Never perform destructive data operations. No `DROP TABLE`/`DROP DATABASE`/`TRUNCATE`, no
  unconditional `DELETE`, no dropping columns or tables that hold data.
- Only additive, reversible schema migrations. Never run `prisma migrate reset`,
  `prisma db push --force-reset`, or any command that resets or wipes a database.
- Keep the code very simple: prefer the smallest change that satisfies the request.
- If the application cannot build or render, do not open or approve a pull request.
- Never commit secrets, credentials, or tokens.
