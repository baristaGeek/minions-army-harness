"""Spec Kit pipeline steps."""

from __future__ import annotations

from minions_army.application.services.orchestration_service import PipelineStep
from minions_army.core.runtime.steps.bootstrap import SpecKitBootstrapStep
from minions_army.core.runtime.steps.checkout_branch import CheckoutBranchStep
from minions_army.core.runtime.steps.clone_repository import CloneRepositoryStep
from minions_army.core.runtime.steps.commit import CommitStep
from minions_army.core.runtime.steps.configure_git import ConfigureGitStep
from minions_army.core.runtime.steps.constitution_preparation import ConstitutionPreparationStep
from minions_army.core.runtime.steps.initialize_workspace import InitializeWorkspaceStep
from minions_army.core.runtime.steps.pull_request import PullRequestStep
from minions_army.core.runtime.steps.push import PushStep
from minions_army.core.runtime.steps.review_merge_deploy import ReviewMergeDeployStep
from minions_army.core.runtime.steps.speckit_constitution import SpeckitConstitutionStep
from minions_army.core.runtime.steps.speckit_implementation import SpeckitImplementationStep
from minions_army.core.runtime.steps.speckit_planner import SpeckitPlannerStep
from minions_army.core.runtime.steps.speckit_specification import SpeckitSpecificationStep
from minions_army.core.runtime.steps.speckit_tasks import SpeckitTasksStep
from minions_army.core.runtime.steps.verify_build import VerifyBuildStep
from minions_army.infrastructure.pipeline_steps.base import PipelineStepsProvider


class SpecKitPipelineStepsProvider(PipelineStepsProvider):
    name = "speckit"

    def build(self) -> list[PipelineStep]:
        return [
            InitializeWorkspaceStep(),
            CloneRepositoryStep(),
            CheckoutBranchStep(),
            ConfigureGitStep(),
            ConstitutionPreparationStep(),
            SpecKitBootstrapStep(),
            SpeckitConstitutionStep(),
            SpeckitSpecificationStep(),
            SpeckitPlannerStep(),
            SpeckitTasksStep(),
            SpeckitImplementationStep(),
            VerifyBuildStep(),
            CommitStep(),
            PushStep(),
            PullRequestStep(),
            ReviewMergeDeployStep(),
        ]
