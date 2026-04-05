"""Classifier engine behavior tests."""

# pylint: disable=missing-function-docstring

from __future__ import annotations

from pathlib import Path

from torrent_content_classifier.classifier import TorrentClassifier
from torrent_content_classifier.models import TorrentFile, TorrentRecord


def _record(name: str, files: list[tuple[str, int]]) -> TorrentRecord:
    return TorrentRecord(
        info_hash="test-hash",
        torrent_name=name,
        file_list=[TorrentFile(path=path, size=size) for path, size in files],
    )


def test_fallback_classifies_single_flac_track() -> None:
    record = _record(
        "Faye.Wong.To.Youth.Collection.2013.FLAC",
        [("track01.flac", 15_000_000)],
    )
    result = TorrentClassifier().classify(record)
    assert result.kind == "music"
    assert result.subtype == "music_single_track_flac"


def test_fallback_classifies_tv_season() -> None:
    record = _record(
        "Community.S03.2160p.WEB-DL",
        [
            ("Community.S03E01.2160p.WEB-DL.mkv", 2_000_000_000),
            ("Community.S03E02.2160p.WEB-DL.mkv", 2_100_000_000),
        ],
    )
    result = TorrentClassifier().classify(record)
    assert result.kind == "video"
    assert result.subtype == "video_tv_season"


def test_yaml_rules_take_priority_over_fallback(tmp_path: Path) -> None:
    rules_path = tmp_path / "override_rules.yaml"
    rules_path.write_text(
        "- id: override.flac\n"
        "  priority: 9999\n"
        "  enabled: true\n"
        "  when:\n"
        "    ext_any: [\".flac\"]\n"
        "  then:\n"
        "    kind: archive\n"
        "    subtype: archive_test_override\n"
        "    confidence: 0.99\n"
        "    reason: force override for test\n",
        encoding="utf-8",
    )

    record = _record(
        "Any.FLAC.Record",
        [
            ("01.flac", 10_000_000),
            ("02.flac", 12_000_000),
        ],
    )
    result = TorrentClassifier(rules_path=rules_path).classify(record)
    assert result.kind == "archive"
    assert result.subtype == "archive_test_override"
    assert result.matched_rule_ids == ["override.flac"]


def test_unknown_no_rule_match_when_no_yaml_hit() -> None:
    record = _record("NoSignal", [("readme.bin", 1)])
    result = TorrentClassifier().classify(record)
    assert result.subtype in {"unknown_no_rule_match", "unknown_misc"}
