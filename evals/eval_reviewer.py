"""Score the DSPy reviewer on the held-out set.

Reports accuracy plus the two rates that matter: false-approve (dangerous diff
waved through) and false-block (benign change rejected). Compares zero-shot to a
compiled program when one is provided.

Usage (from repo root, with ANTHROPIC_API_KEY set):
    python -m evals.eval_reviewer
    python -m evals.eval_reviewer --compiled evals/compiled_reviewer.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

import dspy

from evals.metric import summarize
from evals.reviewer_dataset import load_examples, train_dev_split
from minions_army.infrastructure.reviewers.dspy import ReviewPR, configure_reviewer_lm


def _run(program: dspy.Module, devset: list[dspy.Example]) -> dict[str, float]:
    preds = [program(user_request=e.user_request, pr_diff=e.pr_diff) for e in devset]
    return summarize(devset, preds)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiled", type=Path, default=None, help="Path to a compiled program")
    args = parser.parse_args()

    configure_reviewer_lm()
    _, devset = train_dev_split(load_examples())

    zero_shot = dspy.ChainOfThought(ReviewPR)
    print("== zero-shot ==")
    print(_run(zero_shot, devset))

    if args.compiled and args.compiled.exists():
        compiled = dspy.ChainOfThought(ReviewPR)
        compiled.load(str(args.compiled))
        print(f"== compiled ({args.compiled}) ==")
        print(_run(compiled, devset))


if __name__ == "__main__":
    main()
