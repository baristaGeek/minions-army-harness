Prepare the selected constitution for the current minion workspace.

Rules:

- Use the selected SDD framework `speckit` and run `speckit-constitution` before producing the JSON response.
- Read the constitution file from `{{CONSTITUTION_FILE}}` in the repository root.
- Do not edit application source code in this stage.
- Return valid JSON only, without markdown fences or commentary.
- Use this schema:
  {
    "summary": string,
    "plan": string,
    "actions": string[],
    "validation": string[],
    "risks_follow_up": string[]
  }
