"""Load and validate YAML rules into normalized rule objects."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .models import Rule, RuleThen


class RuleRegistryError(ValueError):
    """Raised when rule YAML content is invalid."""


_REQUIRED_RULE_FIELDS = ("id", "priority", "enabled", "when", "then")
_REQUIRED_THEN_FIELDS = ("kind", "subtype", "confidence", "reason")


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    """Ensure value is mapping and return a mutable dict copy."""
    if not isinstance(value, Mapping):
        raise RuleRegistryError(f"{context} must be a mapping")
    return dict(value)


def _build_rule(payload: Mapping[str, Any]) -> Rule:
    """Build one validated rule object from raw payload."""
    missing_rule_fields = [field for field in _REQUIRED_RULE_FIELDS if field not in payload]
    if missing_rule_fields:
        missing = ", ".join(missing_rule_fields)
        raise RuleRegistryError(f"missing required rule fields: {missing}")

    then_payload = _require_mapping(payload["then"], f"rule {payload['id']!r} then")
    missing_then_fields = [field for field in _REQUIRED_THEN_FIELDS if field not in then_payload]
    if missing_then_fields:
        missing = ", ".join(missing_then_fields)
        rule_id = payload["id"]
        raise RuleRegistryError(
            f"missing required then fields for rule {rule_id!r}: {missing}"
        )

    guards_payload = payload.get("guards", {})
    guards = _require_mapping(guards_payload, f"rule {payload['id']!r} guards")

    return Rule(
        id=str(payload["id"]),
        priority=int(payload["priority"]),
        enabled=bool(payload["enabled"]),
        when=_require_mapping(payload["when"], f"rule {payload['id']!r} when"),
        then=RuleThen(
            kind=str(then_payload["kind"]),
            subtype=str(then_payload["subtype"]),
            confidence=float(then_payload["confidence"]),
            reason=str(then_payload["reason"]),
        ),
        guards=guards,
    )


def load_rule_set(path: Path) -> list[Rule]:
    """Load enabled rules from YAML sorted by priority descending."""
    raw = path.read_text(encoding="utf-8")
    payload = yaml.safe_load(raw)
    if not isinstance(payload, list):
        raise RuleRegistryError("rule file root must be a list")

    rules: list[Rule] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise RuleRegistryError(f"rule item at index {index} must be a mapping")
        rule = _build_rule(item)
        if rule.enabled:
            rules.append(rule)

    return sorted(rules, key=lambda rule: rule.priority, reverse=True)
