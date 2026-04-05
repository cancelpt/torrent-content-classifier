"""Parity tests for music rule batch."""

# pylint: disable=missing-function-docstring

from torrent_content_classifier.classifier import TorrentClassifier
from torrent_content_classifier.models import TorrentFile, TorrentRecord


def test_music_flac_with_log_parity() -> None:
    record = TorrentRecord(
        info_hash="x",
        torrent_name="Artist.Album.2020.FLAC",
        file_list=[
            TorrentFile(path="01.flac", size=10),
            TorrentFile(path="02.flac", size=11),
            TorrentFile(path="rip.log", size=2_000),
        ],
    )
    result = TorrentClassifier().classify(record)
    assert result.subtype == "music_flac_with_log"
    assert result.matched_rule_ids


def test_music_single_track_m4a_not_promoted_to_m4a_lossy() -> None:
    record = TorrentRecord(
        info_hash="x2",
        torrent_name="Single.Track",
        file_list=[
            TorrentFile(path="01-track.m4a", size=10),
            TorrentFile(path="cover.jpg", size=10),
        ],
    )
    result = TorrentClassifier().classify(record)
    assert result.subtype == "music_single_track_m4a"


def test_music_flac_no_log_with_small_txt_stays_no_log() -> None:
    record = TorrentRecord(
        info_hash="x3",
        torrent_name="Artist.Album",
        file_list=[
            TorrentFile(path="01.flac", size=10),
            TorrentFile(path="02.flac", size=11),
            TorrentFile(path="readme.txt", size=300),
        ],
    )
    result = TorrentClassifier().classify(record)
    assert result.subtype == "music_flac_no_log"


def test_music_vinyl_name_without_txt_not_forced_to_vinyl() -> None:
    record = TorrentRecord(
        info_hash="x4",
        torrent_name="Some Album [VINYL-FLAC]",
        file_list=[
            TorrentFile(path="01.flac", size=10),
            TorrentFile(path="02.flac", size=11),
        ],
    )
    result = TorrentClassifier().classify(record)
    assert result.subtype == "music_flac_no_log"


def test_music_flac_with_video_sidecar_stays_video() -> None:
    record = TorrentRecord(
        info_hash="x5",
        torrent_name="Album.With.Video",
        file_list=[
            TorrentFile(path="01.flac", size=10),
            TorrentFile(path="02.flac", size=11),
            TorrentFile(path="rip.log", size=2_000),
            TorrentFile(path="extra/pv.avi", size=100),
        ],
    )
    result = TorrentClassifier().classify(record)
    assert result.kind == "video"
    assert result.subtype == "video_movie"


def test_music_wav_cue_with_video_sidecar_stays_video() -> None:
    record = TorrentRecord(
        info_hash="x6",
        torrent_name="Album.With.ExtraVideo",
        file_list=[
            TorrentFile(path="album.wav", size=10),
            TorrentFile(path="album.cue", size=100),
            TorrentFile(path="extra/pv.mov", size=100),
        ],
    )
    result = TorrentClassifier().classify(record)
    assert result.kind == "video"
    assert result.subtype == "video_movie"


def test_music_redundant_format_not_demoted_to_bad_format() -> None:
    record = TorrentRecord(
        info_hash="x7",
        torrent_name="Track.Multi.Format",
        file_list=[
            TorrentFile(path="track01.flac", size=10),
            TorrentFile(path="track01.ape", size=11),
            TorrentFile(path="track01.mp3", size=12),
        ],
    )
    result = TorrentClassifier().classify(record)
    assert result.subtype == "music_redundant_format"


def test_music_single_track_flac_with_sidecar_hits_rule() -> None:
    record = TorrentRecord(
        info_hash="x8",
        torrent_name="Single.Track.FLAC",
        file_list=[
            TorrentFile(path="song.flac", size=10),
            TorrentFile(path="cover.jpg", size=10),
            TorrentFile(path="song.lrc", size=10),
        ],
    )
    result = TorrentClassifier().classify(record)
    assert result.subtype == "music_single_track_flac"
    assert result.matched_rule_ids


def test_music_flac_with_log_and_many_images_hits_rule() -> None:
    record = TorrentRecord(
        info_hash="x9",
        torrent_name="Album.FLAC",
        file_list=[
            TorrentFile(path="disc/01.flac", size=10),
            TorrentFile(path="disc/02.flac", size=11),
            TorrentFile(path="disc/03.flac", size=12),
            TorrentFile(path="disc/rip.log", size=2_000),
            TorrentFile(path="art/booklet-01.jpg", size=10),
            TorrentFile(path="art/booklet-02.jpg", size=10),
            TorrentFile(path="art/cover.jpg", size=10),
        ],
    )
    result = TorrentClassifier().classify(record)
    assert result.subtype == "music_flac_with_log"
    assert result.matched_rule_ids
