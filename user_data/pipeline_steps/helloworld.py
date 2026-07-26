"""HelloWorld pipeline steps."""

from __future__ import annotations

from minions_army.application.services.orchestration_service import PipelineStep
from minions_army.core.runtime.steps.helloworld import HelloWorldStep
from minions_army.infrastructure.pipeline_steps.base import PipelineStepsProvider


class HelloWorldPipelineStepsProvider(PipelineStepsProvider):
    name = "helloworld"

    def build(self) -> list[PipelineStep]:
        return [
            HelloWorldStep(),
        ]
