"""Parity tests for misc rule batch."""

# pylint: disable=missing-function-docstring

from torrent_content_classifier.classifier import TorrentClassifier
from torrent_content_classifier.models import TorrentFile, TorrentRecord


def test_comic_archive_parity() -> None:
    record = TorrentRecord(
        info_hash="x",
        torrent_name="[Manga][Vol.01-Vol.02]",
        file_list=[
            TorrentFile(path="Vol.01.zip", size=10),
            TorrentFile(path="Vol.02.zip", size=10),
        ],
    )
    result = TorrentClassifier().classify(record)
    assert result.subtype == "comic_archive"
    assert result.matched_rule_ids


def test_zip_plus_pdf_prefers_ebook_pdf_collection() -> None:
    record = TorrentRecord(
        info_hash="x2",
        torrent_name="[Vol.01-Vol.07][ZIP+PDF]",
        file_list=[
            TorrentFile(path="zip/Vol.01.zip", size=10),
            TorrentFile(path="zip/Vol.02.zip", size=10),
            TorrentFile(path="pdf/Vol.01.pdf", size=10),
            TorrentFile(path="pdf/Vol.02.pdf", size=10),
        ],
    )
    result = TorrentClassifier().classify(record)
    assert result.kind == "ebook"
    assert result.subtype == "ebook_pdf_collection"
