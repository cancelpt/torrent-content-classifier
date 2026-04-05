"""Parity tests for video rule batch."""

# pylint: disable=missing-function-docstring

from torrent_content_classifier.classifier import TorrentClassifier
from torrent_content_classifier.models import TorrentFile, TorrentRecord


def test_video_tv_season_parity() -> None:
    record = TorrentRecord(
        info_hash="x",
        torrent_name="Community.S03.2160p.WEB-DL",
        file_list=[
            TorrentFile(path="Community.S03E01.2160p.WEB-DL.mkv", size=10),
            TorrentFile(path="Community.S03E02.2160p.WEB-DL.mkv", size=10),
        ],
    )
    result = TorrentClassifier().classify(record)
    assert result.subtype == "video_tv_season"
    assert result.matched_rule_ids


def test_video_tv_episode_parity() -> None:
    record = TorrentRecord(
        info_hash="x2",
        torrent_name="Community Episode 1",
        file_list=[
            TorrentFile(path="Community.S03E01.2160p.WEB-DL.mkv", size=10),
        ],
    )
    result = TorrentClassifier().classify(record)
    assert result.subtype == "video_tv_episode"
    assert result.matched_rule_ids


def test_video_adult_movie_parity() -> None:
    record = TorrentRecord(
        info_hash="x3",
        torrent_name="FC2-PPV-1234567 1080p",
        file_list=[
            TorrentFile(path="FC2-PPV-1234567-1080p.mp4", size=10),
        ],
    )
    result = TorrentClassifier().classify(record)
    assert result.subtype == "video_adult_movie"
    assert result.matched_rule_ids


def test_video_movie_parity() -> None:
    record = TorrentRecord(
        info_hash="x4",
        torrent_name="Movie.2024.1080p.BluRay",
        file_list=[
            TorrentFile(path="Movie.2024.1080p.BluRay.mkv", size=10),
        ],
    )
    result = TorrentClassifier().classify(record)
    assert result.subtype == "video_movie"
    assert result.matched_rule_ids
