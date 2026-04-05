"""Regression test for alignment report metrics."""

# pylint: disable=missing-function-docstring

import importlib.util
import json
from pathlib import Path

ALIGNMENT_REPORT_PATH = Path(__file__).resolve().parents[1] / "tools" / "alignment_report.py"
SPEC = importlib.util.spec_from_file_location("alignment_report", ALIGNMENT_REPORT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

evaluate = MODULE.evaluate


def test_alignment_report_contains_fallback_metrics(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    expected_path = tmp_path / "expected.json"

    input_path.write_text(
        json.dumps(
            {
                "a": {
                    "torrent_name": "sample",
                    "file_list": [{"path": "a.flac", "size": 10}],
                }
            }
        ),
        encoding="utf-8",
    )
    expected_path.write_text(
        json.dumps(
            [
                {
                    "info_hash": "a",
                    "kind": "music",
                    "subtype": "music_single_track_flac",
                }
            ]
        ),
        encoding="utf-8",
    )

    report = evaluate(input_path, expected_path)
    assert "rule_hit_count" in report
    assert "fallback_hit_count" in report
    assert "fallback_hit_rate" in report
