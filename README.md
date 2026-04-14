# torrent-content-classifier

[![CI and Deploy Web App](https://github.com/cancelpt/torrent-content-classifier/actions/workflows/pages.yml/badge.svg?branch=main)](https://github.com/cancelpt/torrent-content-classifier/actions/workflows/pages.yml)

[Online Demo](https://cancelpt.github.io/torrent-content-classifier/)

[简体中文文档](README.zh-CN.md)

Rule-first torrent content classifier driven by YAML rules, with a minimal built-in fallback safety net.

## Install

```bash
pip install -e .
```

## Quick Start

```bash
python -m torrent_content_classifier classify \
  --input input.json \
  --output output.json \
  --summary
```

## Use as a Python Package

```python
from torrent_content_classifier import (
    TorrentClassifier,
    TorrentRecord,
    get_default_rules_path,
)

classifier = TorrentClassifier()  # or TorrentClassifier(rules_path="my_rules.yaml")
record = TorrentRecord.from_mapping(
    "demo_hash",
    {
        "torrent_name": "Example.Movie.2025.1080p.BluRay.x264",
        "file_list": [
            {"path": "Example.Movie.2025.1080p.BluRay.x264.mkv", "size": 2147483648}
        ],
    },
)

result = classifier.classify(record)
print(result.to_dict())
print(result.normalized_kind, result.normalized_music_subtype)
print(get_default_rules_path())
```

## Use Custom Rules

```bash
python -m torrent_content_classifier classify \
  --input input.json \
  --output output.json \
  --rules-file ./my_rules.yaml \
  --include-indicators
```

## Rule Schema

Each YAML rule item supports:

- `id` (required, string)
- `priority` (required, int)
- `enabled` (required, bool)
- `when` (required, condition tree)
- `then` (required, result mapping)
- `guards` (optional, condition tree; matched means block this rule)

`then` fields:

- `kind` (string)
- `subtype` (string)
- `confidence` (float)
- `reason` (string)

## Supported Operators

Tree operators:

- `all: [...]`
- `any: [...]`
- `not: [...]`

Leaf operators:

- `ext_any: [".mkv", ".mp4"]`
- `ext_all: [".iso", ".mds"]`
- `name_regex: "dvd|bluray"`
- `total_files_gte: 2`
- `total_files_lte: 10`
- `size_gte: 1073741824`
- `feature_gte: {season_episode_hits: 2}`
- `feature_eq: {video_file_count: 1}`
- `ext_count_gte: {".flac": 2}`
- `dominant_extension_in: [".flac", ".m4a"]`

## Rule Selection

When multiple rules match, final decision order is:

1. Higher `priority`
2. Higher `confidence`
3. Higher condition specificity

If no rule is selected, classifier falls back to built-in safety logic and may output subtype like `unknown_misc`.

## Output Fields

Each record includes:

- `info_hash`
- `torrent_name`
- `kind`
- `subtype`
- `normalized_kind`
- `normalized_music_subtype`
- `confidence`
- `reasons`
- `matched_rule_ids`
- `trace_id`
- `indicators` (when `--include-indicators`)

## Regression Workflow

Generate alignment report:

```bash
PYTHONPATH=src python tools/alignment_report.py
```

Validate rollout thresholds:

```bash
python tools/check_alignment_thresholds.py
```

Current threshold config is in `tools/alignment_thresholds.json`.

## Development Checks

```bash
ruff check src tests tools
pytest -q
pylint src/torrent_content_classifier tools tests
```

## Web App (TypeScript)

```bash
cd web/app
npm install
npm run dev
```

Then open the local URL printed by Vite (usually `http://localhost:5173`) and drag a `.torrent` file.

Production build + GitHub Pages deployment is handled by [`.github/workflows/pages.yml`](.github/workflows/pages.yml).
