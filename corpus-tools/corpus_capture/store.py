"""Day-file appender.

Events land as one JSON line per event in
``$CORPUS_CAPTURE_DIR/<utc-date>.jsonl`` (default ``~/.claude/capture``).

The write is a single ``os.write`` of ``json + "\\n"`` to a fd opened with
``O_APPEND | O_CREAT``. On Linux, an ``O_APPEND`` write of a buffer smaller
than ``PIPE_BUF`` is atomic, so concurrent hook fires cannot interleave lines.
"""

import datetime
import json
import os

DEFAULT_DIR = os.path.expanduser("~/.claude/capture")


def capture_dir() -> str:
    return os.environ.get("CORPUS_CAPTURE_DIR") or DEFAULT_DIR


def _utc_date() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def day_file_path(directory: str | None = None) -> str:
    """Path to today's UTC day-file under ``directory`` (default capture dir)."""
    return os.path.join(directory or capture_dir(), f"{_utc_date()}.jsonl")


def append_event(event: dict, directory: str | None = None) -> str:
    """Append one serialized event line to today's UTC day-file.

    ``directory`` overrides the default capture dir (used by the Alfred export
    to write into ``$CORPUS_ALFRED_DIR``). Returns the day-file path written.
    Creates the directory if missing.
    """
    directory = directory or capture_dir()
    os.makedirs(directory, exist_ok=True)
    path = day_file_path(directory)

    # separators keep one line per event; the ": " (space after colon) makes
    # the day-file greppable for `"key": value` shapes without a JSON parser.
    line = json.dumps(event, ensure_ascii=False, separators=(",", ": ")) + "\n"
    data = line.encode("utf-8")

    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    return path
