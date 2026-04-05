"""Feature extraction helpers for torrent metadata classification."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .models import TorrentRecord

SEASON_EPISODE_RE = re.compile(r"\bs\d{1,2}[-_. ]*e\d{1,3}\b", flags=re.IGNORECASE)
SEASON_RE = re.compile(r"\bs\d{1,2}\b", flags=re.IGNORECASE)
VOLUME_RE = re.compile(r"\b(?:vol(?:ume)?|v)[-_. ]?\d{1,3}\b", flags=re.IGNORECASE)
BLURAY_RE = re.compile(r"\b(?:blu[- ]?ray|bdmv|uhd|remux)\b", flags=re.IGNORECASE)
DVD_RE = re.compile(r"\b(?:dvd|vob|ifo|bup)\b", flags=re.IGNORECASE)
RESOLUTION_RE = re.compile(r"\b(?:720|1080|1440|2160|4320)p\b", flags=re.IGNORECASE)
ADULT_CODE_RE = re.compile(
    r"\b(?:fc2[-_ ]?ppv[-_ ]?\d{4,7}|[a-z]{2,6}-\d{2,5})\b",
    flags=re.IGNORECASE,
)
ADULT_HINT_RE = re.compile(r"\b(?:dmm|fc2|carib|heyzo|1pondo|mteam|jav)\b", flags=re.IGNORECASE)
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".ts", ".m2ts", ".vob"}


@dataclass
class TorrentFeatures:  # pylint: disable=too-many-instance-attributes
    """Derived features used by the rule evaluator and fallback logic."""

    total_files: int
    total_size: int
    ext_counter: Counter[str] = field(default_factory=Counter)
    largest_file_size: int = 0
    largest_file_ext: str = ""
    season_episode_hits: int = 0
    season_hits: int = 0
    volume_hits: int = 0
    bluray_hits: int = 0
    dvd_hits: int = 0
    resolution_hits: int = 0
    adult_hits: int = 0
    video_file_count: int = 0

    def ext_count(self, extensions: set[str]) -> int:
        """Count files whose extension is in the provided set."""
        return sum(self.ext_counter.get(ext, 0) for ext in extensions)

    @property
    def dominant_extension(self) -> str:
        """Return the most frequent extension in the record."""
        if not self.ext_counter:
            return ""
        return self.ext_counter.most_common(1)[0][0]


def _scan_files(record: TorrentRecord) -> tuple[Counter[str], int, int, str]:
    """Aggregate extension counts and size stats from file list."""
    ext_counter: Counter[str] = Counter()
    total_size = 0
    largest_file_size = 0
    largest_file_ext = ""

    for torrent_file in record.file_list:
        ext = torrent_file.extension
        if ext:
            ext_counter[ext] += 1
        total_size += torrent_file.size
        if torrent_file.size > largest_file_size:
            largest_file_size = torrent_file.size
            largest_file_ext = ext

    return ext_counter, total_size, largest_file_size, largest_file_ext


def _count_text_hits(text_blobs: list[str]) -> dict[str, int]:
    """Collect regex hit counters from torrent name and file paths."""
    return {
        "season_episode_hits": sum(len(SEASON_EPISODE_RE.findall(blob)) for blob in text_blobs),
        "season_hits": sum(len(SEASON_RE.findall(blob)) for blob in text_blobs),
        "volume_hits": sum(len(VOLUME_RE.findall(blob)) for blob in text_blobs),
        "bluray_hits": sum(len(BLURAY_RE.findall(blob)) for blob in text_blobs),
        "dvd_hits": sum(len(DVD_RE.findall(blob)) for blob in text_blobs),
        "resolution_hits": sum(len(RESOLUTION_RE.findall(blob)) for blob in text_blobs),
        "adult_hits": sum(len(ADULT_HINT_RE.findall(blob)) for blob in text_blobs),
    }


def extract_features(record: TorrentRecord) -> TorrentFeatures:
    """Extract aggregate counters and regex hits from one torrent record."""
    ext_counter, total_size, largest_file_size, largest_file_ext = _scan_files(record)

    text_blobs = [record.torrent_name, *[torrent_file.path for torrent_file in record.file_list]]
    pattern_hits = _count_text_hits(text_blobs)
    adult_hits = pattern_hits["adult_hits"]
    if ADULT_CODE_RE.search(record.torrent_name):
        adult_hits += 1
    video_file_count = sum(ext_counter.get(ext, 0) for ext in VIDEO_EXTENSIONS)

    return TorrentFeatures(
        total_files=len(record.file_list),
        total_size=total_size,
        ext_counter=ext_counter,
        largest_file_size=largest_file_size,
        largest_file_ext=largest_file_ext,
        season_episode_hits=pattern_hits["season_episode_hits"],
        season_hits=pattern_hits["season_hits"],
        volume_hits=pattern_hits["volume_hits"],
        bluray_hits=pattern_hits["bluray_hits"],
        dvd_hits=pattern_hits["dvd_hits"],
        resolution_hits=pattern_hits["resolution_hits"],
        adult_hits=adult_hits,
        video_file_count=video_file_count,
    )
