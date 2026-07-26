Propose the OpenSpec change using the installed proposal skill.

Original user request:

{{MINION_INPUT_MESSAGE}}

Rules:

- Run the `{{SPEC_STAGE_COMMAND}}` command to create the OpenSpec proposal artifacts.
- Create or update the OpenSpec proposal artifacts required for the change.
- Keep scope aligned to the user request.
- Do not begin implementation work in this stage.
- Do not ask the user any questions; make reasonable decisions and keep momentum.
- Follow `{{CONSTITUTION_FILE}}` — especially its Safety and Guardrails section.
- Keep the code very simple: propose the smallest change that satisfies the request. No new
  abstractions, dependencies, or scope beyond what was asked.
- Never propose destructive operations: no `DROP`/`TRUNCATE`/unconditional `DELETE` SQL, no
  destructive or non-additive migrations, no `prisma migrate reset` or `db push --force-reset`.
- If the application cannot render or build, do not propose changes that would open a PR; describe
  the blocker in `risks_follow_up` instead.
- Return valid JSON only, without markdown fences or commentary.
- Use this schema:
  {
    "summary": string,
    "plan": string,
    "actions": string[],
    "validation": string[],
    "risks_follow_up": string[]
  }
