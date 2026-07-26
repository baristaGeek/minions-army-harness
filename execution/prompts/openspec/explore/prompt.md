Explore the requested change using the installed OpenSpec explore skill.

Original user request:

{{MINION_INPUT_MESSAGE}}

Rules:

- Use the installed `openspec-explore` skill.
- Inspect the repository state and identify the OpenSpec change context needed for this request.
- Do not write implementation code in this stage.
- Return valid JSON only, without markdown fences or commentary.
- Use this schema:
  {
    "summary": string,
    "plan": string,
    "actions": string[],
    "validation": string[],
    "risks_follow_up": string[]
  }
