"""Compile (optimize) the DSPy reviewer and save the artifact.

DSPy proposes the "synthetic prompts": BootstrapFewShot bootstraps few-shot
demonstrations from successful traces, and (optionally) MIPROv2 has an LLM
propose candidate instruction rewrites, both selected by ``review_metric``. The
winning program is saved to ``evals/compiled_reviewer.json`` for the runtime to
load via ``MINION_REVIEWER_COMPILED_PATH``.

Usage (from repo root, with ANTHROPIC_API_KEY set):
    python -m evals.optimize_reviewer                 # bootstrap few-shot
    python -m evals.optimize_reviewer --optimizer mipro
"""

from __future__ import annotations

import argparse
from pathlib import Path

import dspy

from evals.metric import review_metric
from evals.reviewer_dataset import load_examples, train_dev_split
from minions_army.infrastructure.reviewers.dspy import ReviewPR, configure_reviewer_lm

OUTPUT_PATH = Path(__file__).parent / "compiled_reviewer.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--optimizer", choices=["bootstrap", "mipro"], default="bootstrap")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    configure_reviewer_lm()
    trainset, devset = train_dev_split(load_examples())
    program = dspy.ChainOfThought(ReviewPR)

    if args.optimizer == "mipro":
        optimizer = dspy.MIPROv2(metric=review_metric, auto="light")
        compiled = optimizer.compile(program, trainset=trainset, valset=devset)
    else:
        optimizer = dspy.BootstrapFewShotWithRandomSearch(
            metric=review_metric,
            max_bootstrapped_demos=4,
            max_labeled_demos=4,
            num_candidate_programs=6,
        )
        compiled = optimizer.compile(program, trainset=trainset, valset=devset)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    compiled.save(str(args.output))
    print(f"Saved compiled reviewer to {args.output}")


if __name__ == "__main__":
    main()
