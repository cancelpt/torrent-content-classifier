# torrent-content-classifier

基于 YAML 规则的种子内容分类器，采用“规则优先 + 最小内置回退”策略。

## 安装

```bash
pip install -e .
```

## 快速开始

```bash
python -m torrent_content_classifier classify \
  --input input.json \
  --output output.json \
  --summary
```

## 作为 Python 包导入使用

```python
from torrent_content_classifier import TorrentClassifier, TorrentRecord

classifier = TorrentClassifier()  # 也可以传入 TorrentClassifier(rules_path="my_rules.yaml")
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
```

## 使用自定义规则 YAML

```bash
python -m torrent_content_classifier classify \
  --input input.json \
  --output output.json \
  --rules-file ./my_rules.yaml \
  --include-indicators
```

## 规则结构

每条规则支持以下字段：

- `id`（必填，字符串）
- `priority`（必填，整数）
- `enabled`（必填，布尔）
- `when`（必填，条件树）
- `then`（必填，命中后的分类结果）
- `guards`（可选，若命中则阻断该规则）

`then` 必填字段：

- `kind`
- `subtype`
- `confidence`
- `reason`

## 条件操作符

逻辑操作符：

- `all: [...]`
- `any: [...]`
- `not: [...]`

叶子操作符：

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

## 命中决策顺序

多条规则同时命中时，按以下顺序选最终结果：

1. `priority` 更高
2. `confidence` 更高
3. 条件特异性更高

若没有规则命中，则进入最小内置回退，常见输出如 `unknown_misc`。

## 输出字段

每条结果包含：

- `info_hash`
- `torrent_name`
- `kind`
- `subtype`
- `confidence`
- `reasons`
- `matched_rule_ids`
- `trace_id`
- `indicators`（开启 `--include-indicators` 时输出）

## 回归对齐流程

生成回归对齐报告：

```bash
PYTHONPATH=src python tools/alignment_report.py
```

执行阈值门禁：

```bash
python tools/check_alignment_thresholds.py
```

阈值配置文件：`tools/alignment_thresholds.json`。

## 开发校验

```bash
ruff check src tests tools
pytest -q
pylint src/torrent_content_classifier tools tests
```

## TypeScript 网页应用

```bash
cd web/app
npm install
npm run dev
```

启动后打开终端打印的本地地址（通常 `http://localhost:5173`），拖入 `.torrent` 文件即可即时分类。

