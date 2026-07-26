# Agent Providers

Each file in this folder is an agent strategy. The config value
`agent.provider_class` points directly to the class to use.

Example:

```yaml
agent:
  provider_class: user_data.agent_providers.kimi.KimiAgentProvider
```

Each provider owns its own runtime contract. Kimi reads `agent.kimi_api_key`
from `user_data/config.yml` or `KIMI_API_KEY` from the process environment,
uses `user_data/kimi_code_home/config.toml` as the template, replaces the
`${KIMI_API_KEY}` placeholder, writes the final config to
`~/.kimi-code/config.toml`, and runs `kimi --prompt`.

Kimi Code CLI must be available as `kimi` in `PATH`. The minion image installs
the npm package `@moonshot-ai/kimi-code` using the `KIMI_CODE_VERSION` Docker
build argument.

Every provider must define a named class:

```python
from minions_army.infrastructure.agents.base import AgentProvider


class KimiAgentProvider(AgentProvider):
    name = "kimi"

    def run(self, request):
        ...
```

See [Configuration Guide](../../docs/CONFIGURATION.md) for complete examples,
provider rules, and the recommended test coverage.
