"""Rule registry schema validation tests."""

# pylint: disable=missing-function-docstring

from pathlib import Path

import pytest

from torrent_content_classifier.rules.registry import RuleRegistryError, load_rule_set


def test_load_rule_set_success() -> None:
    rules = load_rule_set(Path("tests/fixtures/rules/minimal_rules.yaml"))

    assert [rule.id for rule in rules] == [
        "music.uncommon.tak",
        "archive.subtitle.tgz",
    ]


def test_load_rule_set_schema_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad_rules.yaml"
    bad.write_text(
        "- id: broken.rule\n"
        "  priority: 1\n"
        "  enabled: true\n"
        "  when:\n"
        "    ext_any: [\".bad\"]\n"
        "  then:\n"
        "    kind: music\n",
        encoding="utf-8",
    )

    with pytest.raises(RuleRegistryError):
        load_rule_set(bad)
