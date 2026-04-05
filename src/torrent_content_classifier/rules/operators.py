"""Condition tree operators used by YAML rules."""

from __future__ import annotations

import re

_OPERATOR_KEYS = {
    "ext_any",
    "ext_all",
    "name_regex",
    "total_files_gte",
    "total_files_lte",
    "size_gte",
    "feature_gte",
    "feature_eq",
    "ext_count_gte",
    "dominant_extension_in",
}


def _eval_leaf(node: dict, record, features) -> bool:
    """Evaluate one non-branch condition node."""
    if "ext_any" in node:
        result = any(features.ext_counter.get(ext, 0) > 0 for ext in node["ext_any"])
    elif "ext_all" in node:
        result = all(features.ext_counter.get(ext, 0) > 0 for ext in node["ext_all"])
    elif "name_regex" in node:
        result = bool(re.search(node["name_regex"], record.torrent_name, flags=re.IGNORECASE))
    elif "total_files_gte" in node:
        result = features.total_files >= int(node["total_files_gte"])
    elif "total_files_lte" in node:
        result = features.total_files <= int(node["total_files_lte"])
    elif "size_gte" in node:
        result = features.total_size >= int(node["size_gte"])
    elif "feature_gte" in node:
        payload = node["feature_gte"]
        result = all(
            getattr(features, key, -10**18) >= int(value)
            for key, value in payload.items()
        )
    elif "feature_eq" in node:
        payload = node["feature_eq"]
        result = all(getattr(features, key, object()) == value for key, value in payload.items())
    elif "ext_count_gte" in node:
        payload = node["ext_count_gte"]
        result = all(
            features.ext_counter.get(ext, 0) >= int(value)
            for ext, value in payload.items()
        )
    elif "dominant_extension_in" in node:
        result = features.dominant_extension in set(node["dominant_extension_in"])
    else:
        unknown = set(node) - {"all", "any", "not"} - _OPERATOR_KEYS
        result = not unknown
    return result


def evaluate_condition_tree(node: dict, record, features) -> bool:
    """Evaluate a recursive condition tree."""
    if "all" in node:
        return all(evaluate_condition_tree(item, record, features) for item in node["all"])

    if "any" in node:
        return any(evaluate_condition_tree(item, record, features) for item in node["any"])

    if "not" in node:
        return not any(evaluate_condition_tree(item, record, features) for item in node["not"])

    return _eval_leaf(node, record, features)
