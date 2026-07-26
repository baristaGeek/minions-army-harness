"""DSPy-based PR reviewer.

An alternative to the agentic CLI reviewer in ``ReviewMergeDeployStep``.
Instead of a hand-written markdown prompt plus manual JSON parsing, the review
is expressed as a typed :class:`dspy.Signature` and run directly via
:class:`dspy.LM`. DSPy handles the structured output and retries, and the same
program can be *optimized* offline (``evals/optimize_reviewer.py``) so the
prompt/instructions and few-shot demos are learned from a labeled dataset rather
than tuned by hand.

The public entry point :func:`review_pr` returns the exact verdict dict shape the
pipeline already consumes: ``{approved, reasons, blocking_issues, risk_level}``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

import dspy

from minions_army.core.config.loader import config as settings
from minions_army.core.runtime.logging import log_event
from minions_army.infrastructure.agents.loader import load_agent_provider

logger = logging.getLogger(__name__)

# The diff is injected verbatim into the prompt. Cap it so a huge PR can't blow
# past the model context window; the reviewer is told when it has been truncated.
MAX_DIFF_CHARS = 60_000


class ReviewPR(dspy.Signature):
    """Independently review a pull request another agent produced, and decide if it
    is safe to merge to `main` and deploy to production. You did NOT write this
    code. Be skeptical and thorough.

    Set `approved` to false if ANY of the following are present:
    - Destructive database operations: DROP/TRUNCATE/unconditional DELETE SQL,
      destructive or non-additive migrations, `prisma migrate reset`,
      `prisma db push --force-reset`, or anything that could wipe or reset data.
    - Secrets, credentials, or API tokens committed in the diff.
    - Changes that would break the build or prevent the app from rendering.
    - Scope creep well beyond the original request, or unnecessary new
      abstractions/dependencies (the standard is: keep the code very simple).
    - Obvious correctness or security defects.

    If none of these are present and the change reasonably satisfies the request,
    approve it.
    """

    user_request: str = dspy.InputField(desc="The original natural-language change request.")
    pr_diff: str = dspy.InputField(desc="The unified diff under review.")
    approved: bool = dspy.OutputField(desc="True only if the PR is safe to merge and deploy.")
    reasons: list[str] = dspy.OutputField(desc="Short justifications for the decision.")
    blocking_issues: list[str] = dspy.OutputField(
        desc="Concrete blocking problems; empty when approved."
    )
    risk_level: Literal["low", "medium", "high"] = dspy.OutputField()


def build_reviewer() -> dspy.Module:
    """Return the reviewer program, loading an optimized artifact when configured."""
    program: dspy.Module = dspy.ChainOfThought(ReviewPR)
    compiled_path = settings.reviewer.compiled_path
    if compiled_path:
        path = Path(compiled_path)
        if path.exists():
            program.load(str(path))
            log_event(logger, logging.INFO, "reviewer.dspy.compiled.loaded", path=path)
        else:
            log_event(
                logger,
                logging.WARNING,
                "reviewer.dspy.compiled.missing",
                path=path,
                fallback="zero_shot",
            )
    return program


def configure_reviewer_lm() -> None:
    """Point DSPy at the selected agent provider."""
    provider = load_agent_provider(settings.agent.provider_class)
    dspy.configure(
        lm=dspy.LM(
            provider.dspy_model_name(settings.reviewer.model),
            api_key=provider.configured_api_key(settings),
        )
    )


def _verdict_from_prediction(prediction: Any) -> dict[str, Any]:
    """Normalize a DSPy prediction into the pipeline's verdict dict contract."""
    return {
        "approved": bool(prediction.approved),
        "reasons": list(prediction.reasons or []),
        "blocking_issues": list(prediction.blocking_issues or []),
        "risk_level": prediction.risk_level,
    }


def review_pr(
    user_request: str,
    pr_diff: str,
    program: dspy.Module | None = None,
    configure_lm: bool = True,
) -> dict[str, Any]:
    """Review a PR diff and return ``{approved, reasons, blocking_issues, risk_level}``.

    ``program``/``configure_lm`` are injectable for tests (a DummyLM is configured
    by the caller, so pass ``configure_lm=False`` to skip the Anthropic setup).
    """
    if configure_lm:
        configure_reviewer_lm()
    reviewer = program or build_reviewer()

    diff = pr_diff or ""
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n\n[diff truncated for length]"

    prediction = reviewer(user_request=user_request, pr_diff=diff)
    verdict = _verdict_from_prediction(prediction)
    log_event(
        logger,
        logging.INFO,
        "reviewer.dspy.verdict",
        approved=verdict["approved"],
        risk_level=verdict["risk_level"],
    )
    return verdict
