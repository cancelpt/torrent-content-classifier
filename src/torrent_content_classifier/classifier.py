"""Core classifier that applies YAML rules then minimal fallback heuristics."""

from __future__ import annotations

import re
from collections import defaultdict
from importlib import resources
from pathlib import Path
from uuid import uuid4

from .features import extract_features
from .models import ClassificationResult, TorrentRecord
from .rules.evaluator import decide_best, evaluate_rules
from .rules.registry import load_rule_set

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".ts", ".m2ts", ".vob"}
BLURAY_STRUCTURE_EXTENSIONS = {".m2ts", ".bdmv", ".clpi", ".mpls"}
DVD_STRUCTURE_EXTENSIONS = {".vob", ".ifo", ".bup"}
UNCOMMON_MUSIC_EXTENSIONS = {".dsf", ".dff", ".tak", ".tta", ".wv", ".aiff", ".aif"}
MUSIC_EXTENSIONS = {
    ".flac",
    ".wav",
    ".ape",
    ".mp3",
    ".aac",
    ".m4a",
    ".ogg",
    ".wma",
    *UNCOMMON_MUSIC_EXTENSIONS,
}
AUDIOBOOK_EXTENSIONS = {".m4b", ".aax", ".abs"}
EBOOK_EXTENSIONS = {".pdf", ".epub", ".mobi", ".azw3", ".djvu", ".chm", ".fb2", ".lit", ".rtf"}
COMIC_EXTENSIONS = {".cbz", ".cbr"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".bpg"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz"}
SOFTWARE_EXTENSIONS = {".exe", ".msi", ".apk", ".dmg", ".pkg", ".deb", ".rpm", ".appimage"}
DOCUMENT_EXTENSIONS = {".txt", ".md", ".nfo"}

MIN_BLURAY_ISO_SIZE = 10 * 1024 * 1024 * 1024

EXCLUDE_MUSIC_TXT_RE = re.compile(
    r"jieshao|list|info|foo_dr|dr analysis|track|playlist|aucdtect",
    flags=re.IGNORECASE,
)
VINYL_HINT_RE = re.compile(r"vinyl|lineage", flags=re.IGNORECASE)
DR_RE = re.compile(r"\bDR(\d{1,2})\b", flags=re.IGNORECASE)
SUBTITLE_ARCHIVE_HINT_RE = re.compile(r"\bass\b|pgs|subtitle|sub\b|字幕", flags=re.IGNORECASE)
DVD_ISO_HINT_RE = re.compile(r"dvdiso|\bdvd\b|480i|480p|720x480|r2j", flags=re.IGNORECASE)
MUSIC_DISC_HINT_RE = re.compile(
    (
        r"\b(?:ost|soundtrack|drama[ ._-]?cd|album|single|disc\d*|cd)\b"
        r"|サウンドトラック|ドラマcd|特典cd"
    ),
    flags=re.IGNORECASE,
)
SOFTWARE_ISO_HINT_RE = re.compile(
    r"\bsetup|installer|game|tool|utility|desktop|accessor",
    flags=re.IGNORECASE,
)


def _default_rules_resource():
    """Return package default rules resource with Python 3.8-compatible fallback."""
    if hasattr(resources, "files"):
        return resources.files("torrent_content_classifier.rules").joinpath(
            "default_rules.yaml"
        )
    return Path(__file__).resolve().parent / "rules" / "default_rules.yaml"


def get_default_rules_path() -> str:
    """Return default rule resource location for diagnostics/integration checks."""
    return str(_default_rules_resource())


class TorrentClassifier:  # pylint: disable=too-few-public-methods
    """Classify torrent records using rules first and fallback as a safety net."""

    def __init__(self, rules_path: str | Path | None = None):
        self.rules_path = (
            Path(rules_path)
            if rules_path is not None
            else _default_rules_resource()
        )
        self._rules = load_rule_set(self.rules_path)

    @staticmethod
    def _normalize_kind(kind: str, subtype: str) -> str:
        if kind == "video":
            if subtype.startswith("video_bluray"):
                return "bluray"
            if subtype.startswith("video_dvd"):
                return "dvd"
            return "video"

        return {
            "audiobook": "audiobook",
            "document": "document",
            "ebook": "document",
            "image": "photo",
            "comic": "comics",
            "software": "program",
            "music": "music",
        }.get(kind, kind)

    @staticmethod
    def _normalize_music_subtype(subtype: str) -> str:
        if not subtype:
            return "unknown"

        legacy_subtype_map = {
            "music_bad_format": "bad_music",
            "music_mixed": "unknown",
        }
        if subtype in legacy_subtype_map:
            return legacy_subtype_map[subtype]

        if subtype.startswith("music_"):
            return subtype[len("music_") :]

        return subtype

    def classify(self, record: TorrentRecord) -> ClassificationResult:
        """Classify a single torrent record."""
        features = extract_features(record)
        rules_result = self._classify_from_rules(record, features)
        if rules_result is not None and self._should_use_rule_result(rules_result, features):
            return rules_result

        return self._classify_with_minimal_fallback(record, features)

    def _classify_with_minimal_fallback(  # pylint: disable=too-many-return-statements
        self,
        record: TorrentRecord,
        features,
    ) -> ClassificationResult:
        """Run fallback classification only when no rule result is usable."""
        if features.total_files == 0:
            return self._build_result(
                record=record,
                kind="unknown",
                subtype="unknown_empty",
                confidence=0.2,
                reasons=["empty file list"],
                features=features,
            )

        if features.ext_count(AUDIOBOOK_EXTENSIONS) > 0:
            return self._build_result(
                record=record,
                kind="audiobook",
                subtype="audiobook_file",
                confidence=0.93,
                reasons=["detected audiobook extensions"],
                features=features,
            )

        music_count = features.ext_count(MUSIC_EXTENSIONS)
        if music_count > 0:
            subtype, confidence, reasons = self._classify_music(record)
            return self._build_result(
                record=record,
                kind="music",
                subtype=subtype,
                confidence=confidence,
                reasons=reasons,
                features=features,
            )

        if features.ext_count(COMIC_EXTENSIONS) > 0:
            return self._build_result(
                record=record,
                kind="comic",
                subtype="comic_digital",
                confidence=0.95,
                reasons=["detected comic-specific archive extensions (.cbz/.cbr)"],
                features=features,
            )

        ebook_count = features.ext_count(EBOOK_EXTENSIONS)
        if ebook_count > 0:
            subtype = (
                "ebook_pdf_collection"
                if features.ext_counter.get(".pdf", 0) > 0
                else "ebook_collection"
            )
            return self._build_result(
                record=record,
                kind="ebook",
                subtype=subtype,
                confidence=0.92,
                reasons=["detected ebook document formats"],
                features=features,
            )

        software_count = features.ext_count(SOFTWARE_EXTENSIONS)
        if software_count > 0:
            return self._build_result(
                record=record,
                kind="software",
                subtype="software_package",
                confidence=0.97,
                reasons=["detected executable or installer extensions"],
                features=features,
            )

        image_count = features.ext_count(IMAGE_EXTENSIONS)
        if image_count > 0 and image_count == features.total_files:
            return self._build_result(
                record=record,
                kind="image",
                subtype="image_collection",
                confidence=0.9,
                reasons=["all files are image formats"],
                features=features,
            )

        archive_count = features.ext_count(ARCHIVE_EXTENSIONS)
        if archive_count > 0:
            if (
                features.total_files == 1
                and features.dominant_extension == ".tgz"
                and SUBTITLE_ARCHIVE_HINT_RE.search(record.torrent_name)
            ):
                return self._build_result(
                    record=record,
                    kind="archive",
                    subtype="archive_subtitle_pack",
                    confidence=0.88,
                    reasons=["single .tgz archive with subtitle/ASS/PGS markers"],
                    features=features,
                )

            subtype = "comic_archive" if features.volume_hits > 0 else "archive_generic"
            confidence = 0.86 if subtype == "comic_archive" else 0.75
            reason = (
                "multi-volume archive pattern (Vol.xx)"
                if subtype == "comic_archive"
                else "archive formats detected"
            )
            kind = "comic" if subtype == "comic_archive" else "archive"
            return self._build_result(
                record=record,
                kind=kind,
                subtype=subtype,
                confidence=confidence,
                reasons=[reason],
                features=features,
            )

        if features.ext_count(DOCUMENT_EXTENSIONS) > 0:
            return self._build_result(
                record=record,
                kind="document",
                subtype="document_text",
                confidence=0.72,
                reasons=["detected plain text/doc metadata files"],
                features=features,
            )

        return self._build_result(
            record=record,
            kind="unknown",
            subtype="unknown_misc",
            confidence=0.4,
            reasons=["no strong extension-based signal"],
            features=features,
        )

    def _should_use_rule_result(self, rules_result: ClassificationResult, features) -> bool:
        """Apply compatibility guards before accepting a matched rule."""
        iso_count = features.ext_counter.get(".iso", 0)

        # Multi-ISO historical TV/DVD packs are noisy; fallback logic is more conservative here.
        if rules_result.subtype in {"software_disk_image", "video_dvd_iso"} and iso_count > 1:
            return False

        # Prefer bluray structure/size heuristic over generic ISO software fallback.
        if rules_result.subtype == "software_disk_image" and self._is_bluray(features):
            return False

        # Keep video-first behavior for mixed video+audio package layouts.
        if (
            rules_result.subtype == "music_uncommon_format"
            and features.ext_count(VIDEO_EXTENSIONS) > 0
        ):
            return False

        return True

    def _is_bluray(self, features) -> bool:
        """Detect Blu-ray structures or large Blu-ray-like ISO images."""
        if features.ext_count(BLURAY_STRUCTURE_EXTENSIONS) > 0:
            return True
        if features.ext_counter.get(".iso", 0) > 0:
            return features.bluray_hits > 0 and features.largest_file_size >= MIN_BLURAY_ISO_SIZE
        return False

    def _classify_from_rules(self, record: TorrentRecord, features) -> ClassificationResult | None:
        """Evaluate rule set and return the best matching rule result."""
        if not self._rules:
            return None

        hits = evaluate_rules(self._rules, record, features)
        best = decide_best(hits)
        if best is None:
            return None

        matched_rule_ids = [hit.rule_id for hit in hits]
        indicators = {
            "total_files": features.total_files,
            "total_size": features.total_size,
            "dominant_extension": features.dominant_extension,
            "season_episode_hits": features.season_episode_hits,
            "season_hits": features.season_hits,
            "volume_hits": features.volume_hits,
            "bluray_hits": features.bluray_hits,
            "adult_hits": features.adult_hits,
            "video_file_count": features.video_file_count,
            "matched_rule_ids": matched_rule_ids,
        }
        normalized_kind = self._normalize_kind(best.kind, best.subtype)
        return ClassificationResult(
            info_hash=record.info_hash,
            torrent_name=record.torrent_name,
            kind=best.kind,
            subtype=best.subtype,
            normalized_kind=normalized_kind,
            normalized_music_subtype=(
                self._normalize_music_subtype(best.subtype)
                if normalized_kind == "music"
                else ""
            ),
            confidence=max(0.0, min(1.0, best.confidence)),
            reasons=[best.reason],
            indicators=indicators,
            matched_rule_ids=matched_rule_ids,
            trace_id=str(uuid4()),
        )

    def _classify_music(  # pylint: disable=too-many-return-statements,too-many-branches
        self,
        record: TorrentRecord,
    ) -> tuple[str, float, list[str]]:
        """Fallback music subtype classifier."""
        audio_exts: list[str] = []
        has_cue = False
        has_redundant = False
        has_log = False
        has_valid_txt = False
        is_vinyl = False
        base_to_exts: dict[str, set[str]] = defaultdict(set)

        for torrent_file in record.file_list:
            ext = torrent_file.extension
            name = torrent_file.name.lower()
            base = name[: -len(ext)] if ext else name

            if ext in MUSIC_EXTENSIONS:
                audio_exts.append(ext)
                base_to_exts[base].add(ext)
                if len(base_to_exts[base]) > 1:
                    has_redundant = True

            if ext in {".log", ".accurip"}:
                has_log = True
            elif ext == ".txt":
                if VINYL_HINT_RE.search(base):
                    is_vinyl = True
                if (
                    not EXCLUDE_MUSIC_TXT_RE.search(base)
                    and torrent_file.size > 1024
                    and not DR_RE.search(base)
                ):
                    has_valid_txt = True

            if ext == ".cue":
                has_cue = True

        if len(audio_exts) == 1 and audio_exts[0] in {".mp3", ".flac", ".m4a"}:
            if audio_exts[0] == ".flac":
                return "music_single_track_flac", 0.95, ["single FLAC track package"]
            if audio_exts[0] == ".m4a":
                return "music_single_track_m4a", 0.93, ["single M4A track package"]
            return "music_single_track_lossy", 0.92, ["single lossy track package"]

        if has_redundant:
            return "music_redundant_format", 0.91, ["same base track with multiple formats"]

        if any(ext in {*UNCOMMON_MUSIC_EXTENSIONS, ".iso"} for ext in audio_exts):
            return "music_uncommon_format", 0.9, ["detected uncommon high-end format"]

        if any(ext in {".ogg", ".wma", ".ape"} for ext in audio_exts):
            return "music_bad_format", 0.88, ["detected lower priority lossy/non-standard format"]

        if ".wav" in audio_exts and has_cue:
            return "music_full_album", 0.92, ["WAV + CUE full-disc pattern"]

        if audio_exts and all(ext == ".flac" for ext in audio_exts) and not is_vinyl:
            if has_log:
                return "music_flac_with_log", 0.97, ["FLAC set with log/accurip proof"]
            if has_valid_txt:
                return (
                    "music_flac_suspected_log",
                    0.86,
                    ["FLAC set with valid info txt but missing log"],
                )
            return "music_flac_no_log", 0.81, ["FLAC set without log file"]

        if audio_exts and all(ext == ".mp3" for ext in audio_exts):
            return "music_mp3_lossy", 0.85, ["pure MP3 package"]

        if audio_exts and all(ext == ".m4a" for ext in audio_exts):
            return "music_m4a_lossy", 0.85, ["pure M4A package"]

        if is_vinyl:
            return "music_vinyl", 0.82, ["vinyl/lineage marker in metadata text"]

        return "music_mixed", 0.74, ["mixed music package with no stronger subtype signal"]

    def _build_result(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        record: TorrentRecord,
        kind: str,
        subtype: str,
        confidence: float,
        reasons: list[str],
        features,
    ) -> ClassificationResult:
        """Build a normalized classification result payload."""
        indicators = {
            "total_files": features.total_files,
            "total_size": features.total_size,
            "dominant_extension": features.dominant_extension,
            "season_episode_hits": features.season_episode_hits,
            "season_hits": features.season_hits,
            "volume_hits": features.volume_hits,
            "bluray_hits": features.bluray_hits,
            "adult_hits": features.adult_hits,
            "video_file_count": features.video_file_count,
            "matched_rule_ids": [],
        }
        normalized_kind = self._normalize_kind(kind, subtype)
        return ClassificationResult(
            info_hash=record.info_hash,
            torrent_name=record.torrent_name,
            kind=kind,
            subtype=subtype,
            normalized_kind=normalized_kind,
            normalized_music_subtype=(
                self._normalize_music_subtype(subtype)
                if normalized_kind == "music"
                else ""
            ),
            confidence=max(0.0, min(1.0, confidence)),
            reasons=reasons,
            indicators=indicators,
            matched_rule_ids=[],
            trace_id=str(uuid4()),
        )
