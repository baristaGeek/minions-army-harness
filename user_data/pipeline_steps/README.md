# Pipeline Steps

Each file in this folder is a pipeline step strategy. The config value
`workflow.steps_provider_class` points directly to the class to use.

Examples:

```yaml
workflow:
  steps_provider_class: user_data.pipeline_steps.openspec.OpenSpecPipelineStepsProvider
```

```yaml
workflow:
  steps_provider_class: user_data.pipeline_steps.speckit.SpecKitPipelineStepsProvider
```

Every provider must define a named class:

```python
from minions_army.infrastructure.pipeline_steps.base import PipelineStepsProvider


class CustomPipelineStepsProvider(PipelineStepsProvider):
    name = "custom"

    def build(self):
        return [...]
```

See [Configuration Guide](../../docs/CONFIGURATION.md) for complete examples,
pipeline rules, and the recommended test coverage.
