"""Input/output utilities for reading records and writing classification results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ClassificationResult, TorrentRecord


def load_records(path: str | Path) -> list[TorrentRecord]:
    """Load torrent records from supported JSON formats."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    records: list[TorrentRecord] = []

    if isinstance(data, dict):
        for info_hash, payload in data.items():
            if not isinstance(payload, dict):
                continue
            records.append(TorrentRecord.from_mapping(str(info_hash), payload))
        return records

    if isinstance(data, list):
        for index, payload in enumerate(data):
            if not isinstance(payload, dict):
                continue
            info_hash = str(payload.get("info_hash", index))
            records.append(TorrentRecord.from_mapping(info_hash, payload))
        return records

    raise ValueError(f"Unsupported input format in {path!s}")


def load_record_map(path: str | Path) -> dict[str, TorrentRecord]:
    """Load torrent records and index them by info hash."""
    return {record.info_hash: record for record in load_records(path)}


def dump_results(
    path: str | Path, results: list[ClassificationResult], include_indicators: bool = True
) -> None:
    """Write classification results to JSON."""
    payload: list[dict[str, Any]] = [
        result.to_dict(include_indicators=include_indicators) for result in results
    ]
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
