Implement the requested change using the completed specification, plan, and tasks.

Original user request:

{{MINION_INPUT_MESSAGE}}

Rules:

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
- `summary` should describe the implementation result in one short sentence.
- `plan` should be a one-sentence recap of the implementation approach.
- Put each action in execution order.
- Keep each validation item short and concrete.
- Each validation item must name a command or direct check you actually performed.
- Keep each risk or follow-up item only if it matters.
- `commit_message` must be a concise imperative or conventional-commit-style summary.
- `pr_title` must describe the completed change clearly.
- `pr_body` must be real markdown and include summary, validation, and risks/follow-up.
- Use the selected SDD framework `speckit` and run `speckit-implement` before producing the JSON response.
- Do not continue unless the tasks artifact exists and the implementation stage has completed successfully for the selected framework.
- Make the required repository file changes yourself; do not stop at a plan or explanation.
- Before returning your final JSON, verify that the repository actually changed by checking `git status --short` and `git diff --stat`.
- Validate the implementation yourself before finishing by running the smallest relevant test, lint, or build check for the files you changed, and include the exact command or direct check in `validation`.
- If you could not make any code or content change, say so explicitly in `risks_follow_up` and do not claim the change was implemented.
