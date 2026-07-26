# Prompts

`execution/prompts/` contains reusable prompt templates and prompt fragments used to assemble execution workflows.

## Structure

```text
execution/prompts/
  README.md
  shared/
    agent-tools.md
    expected-response-format.md
  speckit/
    constitution/
      prompt.md
    specification/
      prompt.md
    planner/
      prompt.md
    tasks/
      prompt.md
    implementation/
      prompt.md
  openspec/
    constitution/
      prompt.md
    explore/
      prompt.md
    propose/
      prompt.md
    apply/
      prompt.md
```

## Agents

`speckit/` and `openspec/` contain the framework-specific prompt pieces used to assemble the workflow prompt.

Use one folder per framework, then one folder per stage. Shared output and tool references should live under `shared/`.

All agents must return JSON only. The shared response shape includes `summary`, `plan`, `actions`, `validation`, and `risks_follow_up`. The `implementation` and `apply` stages also return `commit_message`, `pr_title`, and `pr_body` so the runtime can create the commit and pull request deterministically.
