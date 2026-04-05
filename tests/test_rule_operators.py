"""Condition tree operator tests."""

# pylint: disable=missing-function-docstring

from torrent_content_classifier.features import extract_features
from torrent_content_classifier.models import TorrentFile, TorrentRecord
from torrent_content_classifier.rules.operators import evaluate_condition_tree


def _record() -> TorrentRecord:
    return TorrentRecord(
        info_hash="x",
        torrent_name="[RAINS] sample subtitle (ASS 1920x1080 PGS).tgz",
        file_list=[TorrentFile(path="sample.tgz", size=100)],
    )


def test_all_any_not_tree() -> None:
    record = _record()
    features = extract_features(record)
    cond = {
        "all": [
            {"ext_all": [".tgz"]},
            {"name_regex": "ass|pgs"},
            {"not": [{"name_regex": "mkv"}]},
        ]
    }
    assert evaluate_condition_tree(cond, record, features)


def test_feature_and_count_operators() -> None:
    record = _record()
    features = extract_features(record)

    assert evaluate_condition_tree({"feature_gte": {"season_episode_hits": 0}}, record, features)
    assert evaluate_condition_tree({"ext_count_gte": {".tgz": 1}}, record, features)
    assert evaluate_condition_tree({"dominant_extension_in": [".tgz"]}, record, features)
