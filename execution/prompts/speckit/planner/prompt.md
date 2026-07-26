Create the plan from the completed specification.

Original user request:

{{MINION_INPUT_MESSAGE}}

Rules:

- Keep the plan focused on sequencing and implementation strategy.
- Do not begin implementation work in this stage.
- Make reasonable decisions without asking for clarification.
- Use the relevant skills when they exist; do not replace them with raw commands if a matching skill is available.
- Use the selected SDD framework `speckit` and run `speckit-plan` before producing the JSON response.
- Do not continue unless the specification artifact exists and the plan artifact is created or updated successfully for the selected framework.
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
- Keep `plan` to one short sentence.
- Put each action in execution order.
- Keep each validation item short and concrete.
- Keep each risk or follow-up item only if it matters.
- Do not include `commit_message`, `pr_title`, or `pr_body`.
