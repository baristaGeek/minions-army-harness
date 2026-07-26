# Execution Profiles

Execution profiles describe the tools and conventions available in a given stack or toolset. They complement `execution/constitutions/`, which defines engineering expectations.

## Structure

```text
execution/constitutions/profiles/
  README.md
  tools/
    agent-tools.md
  angular.yaml
  dotnet.yaml
  golang.yaml
  javascript.yaml
  nodejs.yaml
  python.yaml
  react.yaml
```

## Tool Profiles

Tool profiles describe what commands are available to the agent and what each one is for.

Use tool profiles for:

- Command inventory.
- Tool purpose.
- Agent-side workflow guidance.
- Execution capabilities.

## Stack Profiles

Stack profiles describe the tools and conventions associated with a project technology stack.

Use stack profiles for:

- Language and framework conventions.
- Formatter and linter expectations.
- Test tooling.
- Dependency and package management.

## Separation Of Responsibilities

Tool profiles answer: what commands can the agent use?

Stack profiles answer: what does the target repository use?

Constitutions answer: what engineering behavior is expected?

Future execution policies may combine constitutions, tool profiles, and stack profiles, but composition logic belongs outside this folder.

### Add A Tool Profile

Create a new YAML file under `execution/constitutions/profiles/tools/`.

Keep it focused on command names and the purpose of each command.

### Add A Stack Profile

Create a new YAML file directly under `execution/constitutions/profiles/`.

Use a simple YAML structure that captures stack-specific tooling and conventions.
