"""Load the labeled reviewer dataset as DSPy examples."""

from __future__ import annotations

import json
from pathlib import Path

import dspy

DATASET_PATH = Path(__file__).parent / "datasets" / "reviewer.jsonl"


def load_examples(path: Path | None = None) -> list[dspy.Example]:
    """Read the JSONL dataset into inputs-tagged dspy.Example objects.

    Each row carries ``user_request``/``pr_diff`` inputs plus the gold
    ``approved`` label and a ``category`` tag (``benign`` or a block reason).
    """
    path = path or DATASET_PATH
    examples: list[dspy.Example] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        example = dspy.Example(
            user_request=row["user_request"],
            pr_diff=row["pr_diff"],
            approved=bool(row["approved"]),
            category=row.get("category", "benign"),
        ).with_inputs("user_request", "pr_diff")
        examples.append(example)
    return examples


def train_dev_split(
    examples: list[dspy.Example], dev_fraction: float = 0.4
) -> tuple[list[dspy.Example], list[dspy.Example]]:
    """Deterministic, stratified-ish split (interleaved) so both sets see both labels."""
    approved = [e for e in examples if e.approved]
    rejected = [e for e in examples if not e.approved]
    train: list[dspy.Example] = []
    dev: list[dspy.Example] = []
    for group in (approved, rejected):
        cut = max(1, round(len(group) * (1 - dev_fraction)))
        train.extend(group[:cut])
        dev.extend(group[cut:])
    return train, dev
