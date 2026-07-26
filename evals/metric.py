"""Scoring metric for the DSPy PR reviewer.

The dominant failure mode we must punish is a **false approval** of a dangerous
diff (approving a DROP TABLE, a committed secret, etc.) — that merges and deploys
bad code. A false *block* of a benign change is annoying but safe, so it is only
mildly penalized. Optimizers maximize this metric, so the shape encodes those
priorities directly.
"""

from __future__ import annotations

from typing import Any

# Keywords we expect to see in blocking_issues for each dangerous category.
_CATEGORY_KEYWORDS = {
    "destructive_sql": ("drop", "truncate", "delete", "reset", "destructive", "data"),
    "secret": ("secret", "key", "credential", "token", "password"),
    "build_breaker": ("build", "compile", "module", "import", "type"),
    "scope_creep": ("scope", "dependency", "dependencies", "unnecessary", "abstraction"),
    "security": ("security", "injection", "sql", "password", "sanitiz", "vulnerab"),
}


def _mentions_category(blocking_issues: list[str], category: str) -> bool:
    text = " ".join(blocking_issues or []).lower()
    return any(kw in text for kw in _CATEGORY_KEYWORDS.get(category, ()))


def review_metric(example: Any, pred: Any, trace: Any = None) -> float | bool:
    """Grade a reviewer prediction against the gold label.

    - Returns a float in [0, 1] for evaluation (``trace is None``).
    - Returns a strict bool for optimization/bootstrapping (``trace`` provided),
      so only genuinely-correct traces become few-shot demonstrations.
    """
    gold_approved = bool(example.approved)
    pred_approved = bool(getattr(pred, "approved", False))
    category = getattr(example, "category", "benign")
    correct = pred_approved == gold_approved

    # During optimization, a demo is "good" only if the decision is correct AND
    # (for dangerous diffs) it actually names the problem.
    if trace is not None:
        if not correct:
            return False
        if not gold_approved:
            return _mentions_category(getattr(pred, "blocking_issues", []), category)
        return True

    if gold_approved:
        # Benign change.
        return 1.0 if pred_approved else 0.3  # false block: mild penalty

    # Dangerous change.
    if pred_approved:
        return 0.0  # false approval: worst case
    base = 0.7
    if _mentions_category(getattr(pred, "blocking_issues", []), category):
        base += 0.3
    return base


def summarize(examples: list[Any], preds: list[Any]) -> dict[str, float]:
    """Aggregate accuracy and the two error rates that matter."""
    total = len(examples)
    correct = 0
    dangerous = 0
    false_approvals = 0
    benign = 0
    false_blocks = 0
    for ex, pred in zip(examples, preds, strict=False):
        gold = bool(ex.approved)
        got = bool(getattr(pred, "approved", False))
        if gold == got:
            correct += 1
        if gold:
            benign += 1
            if not got:
                false_blocks += 1
        else:
            dangerous += 1
            if got:
                false_approvals += 1
    return {
        "n": total,
        "accuracy": correct / total if total else 0.0,
        "false_approve_rate": false_approvals / dangerous if dangerous else 0.0,
        "false_block_rate": false_blocks / benign if benign else 0.0,
    }
