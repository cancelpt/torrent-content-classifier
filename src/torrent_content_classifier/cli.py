"""Command-line interface for torrent content classification."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from .classifier import TorrentClassifier
from .io import dump_results, load_records
from .models import ClassificationResult


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""
    parser = argparse.ArgumentParser(description="Classify torrents by file list and torrent name.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    classify_parser = subparsers.add_parser("classify", help="Classify torrents from a JSON file.")
    classify_parser.add_argument("--input", "-i", type=Path, required=True, help="Input JSON path.")
    classify_parser.add_argument(
        "--output", "-o", type=Path, help="Output JSON path for classification results."
    )
    classify_parser.add_argument(
        "--summary",
        action="store_true",
        help="Print summary counts by kind/subtype.",
    )
    classify_parser.add_argument(
        "--preview",
        type=int,
        default=10,
        help="Preview first N classification rows in stdout.",
    )
    classify_parser.add_argument(
        "--include-indicators",
        action="store_true",
        help="Include rule indicators in output JSON.",
    )
    classify_parser.add_argument(
        "--rules-file",
        type=Path,
        help="Optional YAML rules file path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "classify":
        return _run_classify(args)

    parser.error(f"Unsupported command: {args.command}")
    return 2


def _run_classify(args: argparse.Namespace) -> int:
    """Execute the classify subcommand."""
    records = load_records(args.input)
    classifier = TorrentClassifier(rules_path=args.rules_file)
    results = [classifier.classify(record) for record in records]

    if args.output:
        dump_results(args.output, results, include_indicators=args.include_indicators)
        print(f"wrote {len(results)} result(s) to {args.output}")

    if args.summary:
        _print_summary(results)

    if args.preview > 0:
        _print_preview(results, limit=args.preview)

    if not args.output and not args.summary and args.preview <= 0:
        print("no output requested; pass --summary or --preview or --output")

    return 0


def _print_summary(results: list[ClassificationResult]) -> None:
    """Print grouped counters by kind and subtype."""
    kind_counter = Counter(result.kind for result in results)
    subtype_counter = Counter(result.subtype for result in results)

    print("kind summary:")
    for name, count in kind_counter.most_common():
        print(f"  {name:12s} {count}")

    print("subtype summary:")
    for name, count in subtype_counter.most_common(12):
        print(f"  {name:24s} {count}")


def _print_preview(results: list[ClassificationResult], limit: int) -> None:
    """Print a fixed-size preview of results."""
    print("preview:")
    for result in results[:limit]:
        print(
            f"  {result.info_hash[:8]}  kind={result.kind:<8} subtype={result.subtype:<24} "
            f"confidence={result.confidence:.2f}"
        )
