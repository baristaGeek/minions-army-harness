"""Base class for user-defined pipeline step providers."""

from __future__ import annotations

from minions_army.application.services.orchestration_service import PipelineStep


class PipelineStepsProvider:
    """Strategy base for building the ordered pipeline steps."""

    name: str

    def build(self) -> list[PipelineStep]:
        """Return the ordered steps for one orchestration request."""
        raise NotImplementedError
