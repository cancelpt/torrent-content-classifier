"""Validate alignment report values against configured quality gates."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    """Check exact-match and fallback-rate thresholds for all datasets."""
    report = json.loads(Path("tmp/alignment_report.json").read_text(encoding="utf-8"))
    thresholds = json.loads(Path("tools/alignment_thresholds.json").read_text(encoding="utf-8"))

    for dataset, gate in thresholds.items():
        dataset_report = report[dataset]
        assert dataset_report["exact_match_rate"] >= gate["min_exact_match_rate"], (
            f"{dataset} exact gate failed: "
            f"{dataset_report['exact_match_rate']} < {gate['min_exact_match_rate']}"
        )
        assert dataset_report["fallback_hit_rate"] <= gate["max_fallback_hit_rate"], (
            f"{dataset} fallback gate failed: "
            f"{dataset_report['fallback_hit_rate']} > {gate['max_fallback_hit_rate']}"
        )

    print("alignment thresholds passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
