"""Rule evaluation and best-hit selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .operators import evaluate_condition_tree


@dataclass(frozen=True)
class RuleHit:
    """A single rule match candidate with ranking metadata."""

    rule_id: str
    priority: int
    confidence: float
    kind: str
    subtype: str
    reason: str
    specificity: int


def _specificity(node: dict[str, Any]) -> int:
    """Estimate condition tree specificity for tie-breaking."""
    if "all" in node:
        return 1 + sum(_specificity(item) for item in node["all"])

    if "any" in node:
        return 1 + sum(_specificity(item) for item in node["any"])

    if "not" in node:
        return 1 + sum(_specificity(item) for item in node["not"])

    return len(node)


def evaluate_rules(rules, record, features) -> list[RuleHit]:
    """Evaluate all enabled rules and collect matches."""
    hits: list[RuleHit] = []
    for rule in rules:
        if not evaluate_condition_tree(rule.when, record, features):
            continue

        if rule.guards and evaluate_condition_tree(rule.guards, record, features):
            continue

        hits.append(
            RuleHit(
                rule_id=rule.id,
                priority=rule.priority,
                confidence=rule.then.confidence,
                kind=rule.then.kind,
                subtype=rule.then.subtype,
                reason=rule.then.reason,
                specificity=_specificity(rule.when),
            )
        )
    return hits


def decide_best(hits: list[RuleHit]) -> RuleHit | None:
    """Pick best rule hit by priority, confidence, then specificity."""
    if not hits:
        return None

    return sorted(
        hits,
        key=lambda item: (item.priority, item.confidence, item.specificity),
        reverse=True,
    )[0]
