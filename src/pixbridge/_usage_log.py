"""JSONL logging for API usage (LLM, image generation, TTS, transcription)."""

import json
import threading
from pathlib import Path

_log_lock = threading.Lock()


def log_usage(path: Path, entry: dict) -> None:
    """Append a single usage entry as one JSON line (thread-safe)."""
    line = json.dumps(entry, default=str) + "\n"
    with _log_lock, open(path, "a", encoding="utf-8") as f:
        f.write(line)
