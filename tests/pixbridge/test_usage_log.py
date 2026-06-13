"""Tests for pixbridge._usage_log — thread-safe JSONL append."""

import json

from pixbridge._usage_log import log_usage


def test_appends_one_json_line_per_entry(tmp_path):
    path = tmp_path / "usage.jsonl"
    log_usage(path, {"provider": "gemini", "tokens": 10})
    log_usage(path, {"provider": "openai", "tokens": 20})

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"provider": "gemini", "tokens": 10}
    assert json.loads(lines[1]) == {"provider": "openai", "tokens": 20}


def test_non_serializable_values_fall_back_to_str(tmp_path):
    path = tmp_path / "usage.jsonl"
    log_usage(path, {"path": tmp_path})  # Path is not JSON-native → default=str

    entry = json.loads(path.read_text(encoding="utf-8"))
    assert entry["path"] == str(tmp_path)
