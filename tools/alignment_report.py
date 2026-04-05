"""Generate regression alignment reports against baseline outputs."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from torrent_content_classifier.classifier import TorrentClassifier
from torrent_content_classifier.models import TorrentRecord


def load_records(path: Path) -> dict[str, TorrentRecord]:
    """Load record map from dictionary or list JSON format."""
    data = json.loads(path.read_text(encoding="utf-8"))
    records: dict[str, TorrentRecord] = {}

    if isinstance(data, dict):
        for info_hash, payload in data.items():
            if isinstance(payload, dict):
                records[str(info_hash)] = TorrentRecord.from_mapping(str(info_hash), payload)
        return records

    if isinstance(data, list):
        for index, payload in enumerate(data):
            if isinstance(payload, dict):
                info_hash = str(payload.get("info_hash", index))
                records[info_hash] = TorrentRecord.from_mapping(info_hash, payload)
        return records

    raise ValueError(f"Unsupported input format: {path}")


def load_expected(path: Path) -> dict[str, tuple[str, str]]:
    """Load expected kind/subtype pairs indexed by info hash."""
    data = json.loads(path.read_text(encoding="utf-8"))
    expected: dict[str, tuple[str, str]] = {}
    if not isinstance(data, list):
        return expected

    for row in data:
        if not isinstance(row, dict):
            continue
        info_hash = str(row.get("info_hash", "")).strip()
        if not info_hash:
            continue
        expected[info_hash] = (str(row.get("kind", "")), str(row.get("subtype", "")))

    return expected


def _new_metrics() -> dict[str, int]:
    """Initialize integer counters used by alignment evaluation."""
    return {
        "total": 0,
        "exact": 0,
        "kind_match": 0,
        "missing_records": 0,
        "rule_hit_count": 0,
        "fallback_hit_count": 0,
    }


def evaluate(input_path: Path, expected_path: Path) -> dict[str, object]:  # pylint: disable=too-many-locals
    """Evaluate classifier outputs against one baseline dataset."""
    records = load_records(input_path)
    expected = load_expected(expected_path)
    classifier = TorrentClassifier()
    metrics = _new_metrics()
    expected_counter: Counter[tuple[str, str]] = Counter()
    predicted_counter: Counter[tuple[str, str]] = Counter()
    fallback_subtype_counter: Counter[str] = Counter()
    rule_id_counter: Counter[str] = Counter()
    mismatches: list[dict[str, str]] = []

    for info_hash, (expected_kind, expected_subtype) in expected.items():
        record = records.get(info_hash)
        if record is None:
            metrics["missing_records"] += 1
            continue

        metrics["total"] += 1
        result = classifier.classify(record)
        predicted_kind = result.kind
        predicted_subtype = result.subtype
        if result.matched_rule_ids:
            metrics["rule_hit_count"] += 1
            rule_id_counter[result.matched_rule_ids[0]] += 1
        else:
            metrics["fallback_hit_count"] += 1
            fallback_subtype_counter[predicted_subtype] += 1

        expected_counter[(expected_kind, expected_subtype)] += 1
        predicted_counter[(predicted_kind, predicted_subtype)] += 1

        if predicted_kind == expected_kind:
            metrics["kind_match"] += 1
        if predicted_kind == expected_kind and predicted_subtype == expected_subtype:
            metrics["exact"] += 1
        elif len(mismatches) < 50:
            mismatches.append(
                {
                    "info_hash": info_hash,
                    "expected_kind": expected_kind,
                    "expected_subtype": expected_subtype,
                    "predicted_kind": predicted_kind,
                    "predicted_subtype": predicted_subtype,
                }
            )

    return {
        "expected_rows": len(expected),
        "records_available": len(records),
        "missing_records_for_expected": metrics["missing_records"],
        "evaluated": metrics["total"],
        "kind_match": metrics["kind_match"],
        "kind_match_rate": (metrics["kind_match"] / metrics["total"])
        if metrics["total"]
        else 0.0,
        "exact_match": metrics["exact"],
        "exact_match_rate": (metrics["exact"] / metrics["total"]) if metrics["total"] else 0.0,
        "rule_hit_count": metrics["rule_hit_count"],
        "fallback_hit_count": metrics["fallback_hit_count"],
        "rule_hit_rate": (metrics["rule_hit_count"] / metrics["total"])
        if metrics["total"]
        else 0.0,
        "fallback_hit_rate": (metrics["fallback_hit_count"] / metrics["total"])
        if metrics["total"]
        else 0.0,
        "top_expected_subtypes": [
            {"kind": kind, "subtype": subtype, "count": count}
            for (kind, subtype), count in expected_counter.most_common(20)
        ],
        "top_predicted_subtypes": [
            {"kind": kind, "subtype": subtype, "count": count}
            for (kind, subtype), count in predicted_counter.most_common(20)
        ],
        "top_fallback_subtypes": [
            {"subtype": subtype, "count": count}
            for subtype, count in fallback_subtype_counter.most_common(20)
        ],
        "top_rule_ids": [
            {"rule_id": rule_id, "count": count}
            for rule_id, count in rule_id_counter.most_common(20)
        ],
        "sample_mismatches": mismatches,
    }


def main() -> int:
    """CLI entrypoint for generating `tmp/alignment_report.json`."""
    tmp = Path("tmp")
    report = {
        "files_list": evaluate(tmp / "files_list.json", tmp / "classification_output.json"),
    }

    output = tmp / "alignment_report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {output}")
    print(
        f"files_list exact: {report['files_list']['exact_match']}/"
        f"{report['files_list']['evaluated']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
