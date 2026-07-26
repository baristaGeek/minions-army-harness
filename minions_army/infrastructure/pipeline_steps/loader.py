"""Load pipeline step providers by class path."""

from __future__ import annotations

import importlib

from minions_army.infrastructure.pipeline_steps.base import PipelineStepsProvider


def load_pipeline_steps_provider(class_path: str) -> PipelineStepsProvider:
    class_path = class_path.strip()
    if not class_path:
        raise SystemExit("workflow.steps_provider_class is required")
    module_name, separator, class_name = class_path.rpartition(".")
    if not separator or not module_name or not class_name:
        raise SystemExit(
            "workflow.steps_provider_class must be a Python class path like "
            "user_data.pipeline_steps.openspec.OpenSpecPipelineStepsProvider"
        )

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise SystemExit(
                f"Cannot import workflow.steps_provider_class '{class_path}'. "
                f"Create {module_name.replace('.', '/')}.py."
            ) from exc
        raise

    provider_class = getattr(module, class_name, None)
    if provider_class is None:
        raise SystemExit(f"{module_name} must define {class_name}")

    steps_provider = provider_class()
    if not isinstance(steps_provider, PipelineStepsProvider):
        raise SystemExit(f"{class_path} must extend PipelineStepsProvider")
    return steps_provider
