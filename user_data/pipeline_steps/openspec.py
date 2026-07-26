"""OpenSpec pipeline steps."""

from __future__ import annotations

from minions_army.application.services.orchestration_service import PipelineStep
from minions_army.core.runtime.steps.bootstrap import OpenSpecBootstrapStep
from minions_army.core.runtime.steps.checkout_branch import CheckoutBranchStep
from minions_army.core.runtime.steps.clone_repository import CloneRepositoryStep
from minions_army.core.runtime.steps.commit import CommitStep
from minions_army.core.runtime.steps.configure_git import ConfigureGitStep
from minions_army.core.runtime.steps.constitution_preparation import ConstitutionPreparationStep
from minions_army.core.runtime.steps.initialize_workspace import InitializeWorkspaceStep
from minions_army.core.runtime.steps.openspec_apply import OpenspecApplyStep
from minions_army.core.runtime.steps.openspec_constitution import OpenspecConstitutionStep
from minions_army.core.runtime.steps.openspec_explore import OpenspecExploreStep
from minions_army.core.runtime.steps.openspec_propose import OpenspecProposeStep
from minions_army.core.runtime.steps.pull_request import PullRequestStep
from minions_army.core.runtime.steps.push import PushStep
from minions_army.core.runtime.steps.review_merge_deploy import ReviewMergeDeployStep
from minions_army.core.runtime.steps.verify_build import VerifyBuildStep
from minions_army.infrastructure.pipeline_steps.base import PipelineStepsProvider


class OpenSpecPipelineStepsProvider(PipelineStepsProvider):
    name = "openspec"

    def build(self) -> list[PipelineStep]:
        return [
            InitializeWorkspaceStep(),
            CloneRepositoryStep(),
            CheckoutBranchStep(),
            ConfigureGitStep(),
            ConstitutionPreparationStep(),
            OpenSpecBootstrapStep(),
            OpenspecConstitutionStep(),
            OpenspecExploreStep(skip=True),
            OpenspecProposeStep(),
            OpenspecApplyStep(),
            VerifyBuildStep(),
            CommitStep(),
            PushStep(),
            PullRequestStep(),
            ReviewMergeDeployStep(),
        ]
