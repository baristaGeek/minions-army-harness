"""Pipeline step implementation."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from minions_army.application.services.orchestration_service import (
    PipelineContext,
)
from minions_army.core.config.loader import config as settings
from minions_army.core.runtime import orchestrator_runtime as runtime
from minions_army.core.runtime.logging import log_event

logger = logging.getLogger("minions_army.core.runtime.orchestrator_runtime")


@dataclass
class ConstitutionPreparationStep:
    name: str = "constitution-prepare"
    skip: bool = False

    def execute(self, context: PipelineContext) -> None:
        def action() -> None:
            result = context.require_result()
            source_root = runtime.CONSTITUTION_ROOT
            template_name = runtime.resolve_constitution_template_name(
                settings.workflow.constitution_depth
            )
            source_file = source_root / template_name
            if not source_file.exists():
                raise SystemExit(f"Constitution template does not exist: {source_file}")
            destination = result.repository_path / "CONSTITUTION.md"
            destination.write_text(source_file.read_text(encoding="utf-8"), encoding="utf-8")
            log_event(
                logger,
                logging.INFO,
                "constitution.prepared",
                template_name=template_name,
                source_file=source_file,
                destination=destination,
            )

        runtime._run_step_with_logging(context, self.name, self.skip, action)
