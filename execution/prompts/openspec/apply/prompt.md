Apply the OpenSpec change using the installed apply-change skill.

Original user request:

{{MINION_INPUT_MESSAGE}}

Rules:

- Run the `{{SPEC_STAGE_COMMAND}}` command to implement the OpenSpec change.
- Implement only what the OpenSpec change already defines.
- Keep changes minimal and scoped. Keep the code very simple.
- Make the required repository file changes yourself; do not stop at a plan or explanation.
- Do not ask the user any questions; make reasonable decisions and keep momentum.
- Follow `{{CONSTITUTION_FILE}}` - especially its Safety and Guardrails section.
- Never perform destructive operations: no `DROP`/`TRUNCATE`/unconditional `DELETE` SQL, no
  destructive or non-additive migrations, no `prisma migrate reset` or `db push --force-reset`.
- Before returning your final JSON, verify that the repository actually changed by checking
  `git status --short` and `git diff --stat`.
- Validate the implementation yourself before finishing by running the smallest relevant test,
  lint, or build check for the files you changed, and include the exact command or direct check
  in `validation`.
- If the application cannot render or build after your change, do not proceed toward a PR; explain
  the blocker in `risks_follow_up`.
- If you could not make any code or content change, say so explicitly in `risks_follow_up` and do not claim the change was implemented.
- Return valid JSON only, without markdown fences or commentary.
- Use this schema:
  {
    "summary": string,
    "plan": string,
    "actions": string[],
    "validation": string[],
    "risks_follow_up": string[],
    "commit_message": string,
    "pr_title": string,
    "pr_body": string
  }
- Each `validation` item must name a command or direct check you actually performed.
