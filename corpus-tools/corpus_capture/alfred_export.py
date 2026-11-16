#!/usr/bin/env python3
"""Alfred Capture Source — export Hermes messages into the Corpus.

Zero Hermes instrumentation: one invocation opens Hermes' ``state.db``
**read-only** (a ``sqlite3`` ``file:…?mode=ro`` URI), selects every message with
``id`` greater than the persisted watermark, joins ``sessions`` for platform
identity (chat/thread/model), redacts content and tool traces through the shared
redaction engine, wraps each row in the pinned envelope (``source: "alfred"``,
``event_type: "message"``), and appends one JSON line per message to the
Remote-host-local day-file ``$CORPUS_ALFRED_DIR/<utc-date>.jsonl`` (the shared store
appender).

The watermark (``{"last_id": <n>}`` in ``…/state/alfred-watermark.json``)
advances only **after** a successful append, and **never rolls back**. That is
the whole point of this source: Hermes rewinds delete rows minutes after writing
them, so exporting on sight and never rewinding the watermark is what makes those
deleted rows survive in the Corpus.

Fields Hermes leaves NULL are omitted from the payload, never faked.

Runs as a plain file (invoked by absolute path), so it bootstraps its own
package directory onto ``sys.path`` before importing sibling modules.
"""

import argparse
import json
import os
import sqlite3
import sys

# --- sys.path bootstrap: make `corpus_capture` importable when run as a file.
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))  # .../corpus_capture
_PKG_ROOT = os.path.dirname(_PKG_DIR)  # package root containing corpus_capture/
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from corpus_capture.envelope import build_envelope  # noqa: E402
from corpus_capture.redact import redact  # noqa: E402
from corpus_capture.store import append_event  # noqa: E402

DEFAULT_DB = os.path.expanduser("~/.hermes/state.db")
DEFAULT_DIR = os.path.expanduser("~/.claude/corpus/alfred")

STATE_SUBDIR = "state"
WATERMARK_NAME = "alfred-watermark.json"

SOURCE = "alfred"
EVENT_TYPE = "message"

# The join that gives every message its platform identity. sessions.id is the
# Hermes session id (its TEXT primary key); messages.session_id references it.
_SELECT = """
    SELECT
        m.id                AS id,
        m.session_id        AS hermes_session_id,
        m.role              AS role,
        m.content           AS content,
        m.tool_calls        AS tool_calls,
        m.tool_name         AS tool_name,
        m.reasoning         AS reasoning,
        s.chat_id           AS chat_id,
        s.thread_id         AS thread_id,
        s.model             AS model
    FROM messages m
    JOIN sessions s ON s.id = m.session_id
    WHERE m.id > ?
    ORDER BY m.id
"""

# Text fields that get scrubbed through the redaction engine. tool_calls is a
# JSON blob that can carry secrets in tool args, so it is redacted too.
_REDACTED_FIELDS = ("content", "tool_calls", "reasoning")

# Payload key -> whether it may be omitted when the source value is NULL.
# id/hermes_session_id/role are always present (NOT NULL in the schema).
_OMIT_IF_NULL = (
    "content",
    "tool_calls",
    "tool_name",
    "reasoning",
    "chat_id",
    "thread_id",
    "model",
)


def _db_path() -> str:
    return os.environ.get("CORPUS_ALFRED_DB") or DEFAULT_DB


def _corpus_dir() -> str:
    return os.environ.get("CORPUS_ALFRED_DIR") or DEFAULT_DIR


def _watermark_path() -> str:
    return os.path.join(_corpus_dir(), STATE_SUBDIR, WATERMARK_NAME)


def _connect_ro(db_path: str) -> sqlite3.Connection:
    """Open ``db_path`` read-only via a ``file:…?mode=ro`` URI.

    A write through this connection raises ``sqlite3.OperationalError`` — the DB
    is never mutated by the export (asserted by the sha256-unchanged test).
    """
    uri = f"file:{db_path}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def _load_watermark() -> int:
    path = _watermark_path()
    if not os.path.exists(path):
        return 0
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return 0
    last = data.get("last_id") if isinstance(data, dict) else None
    return last if isinstance(last, int) else 0


def _save_watermark(last_id: int) -> None:
    path = _watermark_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"last_id": last_id}, fh)
        fh.write("\n")
    os.replace(tmp, path)


def _build_payload(row: sqlite3.Row) -> dict:
    """Shape one message row into the pinned payload.

    Redacts the free-text/tool-trace fields through the shared engine and
    accumulates a single combined redaction report. NULL columns are omitted.
    """
    total_count = 0
    classes: set[str] = set()
    scrubbed: dict[str, str] = {}

    for field in _REDACTED_FIELDS:
        value = row[field]
        if value is None:
            continue
        clean, report = redact(value)
        scrubbed[field] = clean
        total_count += report["count"]
        classes.update(report["classes"])

    payload: dict = {
        "hermes_session_id": row["hermes_session_id"],
        "role": row["role"],
    }

    for key in _OMIT_IF_NULL:
        if row[key] is None:
            continue
        payload[key] = scrubbed.get(key, row[key])

    payload["redactions"] = {"count": total_count, "classes": sorted(classes)}
    return payload


def export(db_path: str, corpus_dir: str) -> int:
    """Export new Hermes messages; return the count of lines appended.

    Watermark advances only after every row of the batch is appended. If an
    append raises (e.g. unwritable corpus dir), the exception propagates and the
    watermark is left untouched so the next run re-exports the whole batch.
    """
    watermark = _load_watermark()
    con = _connect_ro(db_path)
    try:
        rows = con.execute(_SELECT, (watermark,)).fetchall()
    finally:
        con.close()

    if not rows:
        return 0

    appended = 0
    max_id = watermark
    for row in rows:
        envelope = build_envelope(SOURCE, EVENT_TYPE, _build_payload(row))
        append_event(envelope, directory=corpus_dir)
        appended += 1
        max_id = row["id"]

    # Every row landed — advance (never rewind) the watermark.
    _save_watermark(max_id)
    return appended


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Export Hermes messages to the Corpus.")
    parser.parse_args(argv)

    if os.environ.get("CAPTURE_DISABLED") == "1":
        return 0

    try:
        export(_db_path(), _corpus_dir())
    except OSError as exc:
        # Append (or watermark write) failed — e.g. an unwritable corpus dir.
        # The watermark is left un-advanced by design so the next run
        # re-exports the whole batch. Signal the failure via a non-zero exit.
        print(f"alfred_export: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
