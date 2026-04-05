"""Datamodels for torrent input and classification output."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any


@dataclass(frozen=True)
class TorrentFile:
    """A single file entry inside a torrent."""

    path: str
    size: int = 0

    def __post_init__(self) -> None:
        """Normalize path separators and size type."""
        normalized_path = self.path.replace("\\", "/").strip()
        object.__setattr__(self, "path", normalized_path)
        object.__setattr__(self, "size", int(self.size or 0))

    @property
    def name(self) -> str:
        """Return file basename from normalized path."""
        return PurePosixPath(self.path).name

    @property
    def extension(self) -> str:
        """Return lowercase extension with leading dot."""
        return PurePosixPath(self.name.lower()).suffix


@dataclass(frozen=True)
class TorrentRecord:
    """Input record composed of torrent metadata and file list."""

    info_hash: str
    torrent_name: str
    file_list: list[TorrentFile] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, info_hash: str, payload: Mapping[str, Any]) -> TorrentRecord:
        """Build a normalized record from raw mapping payload."""
        torrent_name = str(payload.get("torrent_name", "")).strip()
        raw_files = payload.get("file_list", [])
        files: list[TorrentFile] = []
        if isinstance(raw_files, list):
            for item in raw_files:
                if not isinstance(item, Mapping):
                    continue
                path = str(item.get("path", "")).strip()
                if not path:
                    continue
                files.append(TorrentFile(path=path, size=int(item.get("size", 0) or 0)))

        return cls(info_hash=info_hash, torrent_name=torrent_name, file_list=files)


@dataclass
class ClassificationResult:  # pylint: disable=too-many-instance-attributes
    """Final classification result returned by classifier APIs."""

    info_hash: str
    torrent_name: str
    kind: str
    subtype: str
    confidence: float
    reasons: list[str] = field(default_factory=list)
    indicators: dict[str, Any] = field(default_factory=dict)
    matched_rule_ids: list[str] = field(default_factory=list)
    trace_id: str = ""

    def to_dict(self, include_indicators: bool = True) -> dict[str, Any]:
        """Serialize result to JSON-friendly mapping."""
        payload: dict[str, Any] = {
            "info_hash": self.info_hash,
            "torrent_name": self.torrent_name,
            "kind": self.kind,
            "subtype": self.subtype,
            "confidence": round(float(self.confidence), 3),
            "reasons": self.reasons,
            "matched_rule_ids": self.matched_rule_ids,
            "trace_id": self.trace_id,
        }
        if include_indicators:
            payload["indicators"] = self.indicators
        return payload
