"""Rule evaluator ordering tests."""

# pylint: disable=missing-function-docstring

from pathlib import Path

from torrent_content_classifier.features import extract_features
from torrent_content_classifier.models import TorrentFile, TorrentRecord
from torrent_content_classifier.rules.evaluator import decide_best, evaluate_rules
from torrent_content_classifier.rules.registry import load_rule_set


def test_priority_then_confidence_ordering() -> None:
    rules = load_rule_set(Path("tests/fixtures/rules/minimal_rules.yaml"))
    record = TorrentRecord(
        info_hash="x",
        torrent_name="[RAINS] subtitle pack (ASS 1920x1080 PGS).tgz",
        file_list=[TorrentFile(path="sample.tgz", size=12345)],
    )
    features = extract_features(record)

    hits = evaluate_rules(rules, record, features)
    best = decide_best(hits)
    assert best is not None
    assert best.rule_id == "archive.subtitle.tgz"
