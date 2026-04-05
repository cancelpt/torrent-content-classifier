"""Datamodels for YAML rule definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RuleThen:
    """Classification payload emitted when a rule matches."""

    kind: str
    subtype: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class Rule:
    """Normalized rule object parsed from YAML."""

    id: str
    priority: int
    enabled: bool
    when: dict[str, Any]
    then: RuleThen
    guards: dict[str, Any] = field(default_factory=dict)
