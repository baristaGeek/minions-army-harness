Create the specification for the requested change.

Original user request:

{{MINION_INPUT_MESSAGE}}

Rules:

- Inspect the available tools and use the relevant skills before falling back to raw commands.
- Understand the repository state and the user's request.
- Leave all non-specification work for later agents.
- Make reasonable decisions without asking for clarification.
- Use the relevant skills when they exist; do not replace them with raw commands if a matching skill is available.
- Use the selected SDD framework `speckit` and run `speckit-specify` before producing the JSON response.
- Do not continue unless the specification artifact is created or updated successfully for the selected framework.
- Return valid JSON only, without markdown fences or commentary.
- Use this schema:
  {
    "summary": string,
    "plan": string,
    "actions": string[],
    "validation": string[],
    "risks_follow_up": string[]
  }
- Keep `summary` to one short sentence.
- Keep `plan` empty or brief enough to summarize the next stage.
- Put each action in execution order.
- Keep each validation item short and concrete.
- Keep each risk or follow-up item only if it matters.
- Do not include `commit_message`, `pr_title`, or `pr_body`.
