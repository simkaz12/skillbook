#!/usr/bin/env python3
"""Transcript sweep — idempotent incremental mirror of Claude Code transcripts.

Makes transcript preservation independent of ``SessionEnd`` firing: even if a
session is killed or crashes before its marker hook runs, a later sweep still
copies its complete lines forward. One invocation:

  1. Walks every ``*.jsonl`` under the source root (default ``~/.claude/projects``)
     — both main session transcripts and subagent ``agent-*.jsonl`` files.
  2. For each source file, reads only *complete* lines (up to the last ``\\n``;
     a trailing partial line — a session still mid-write — is left for next time),
     redacts the newly-seen lines through the shared engine, and **appends** them
     to the mirror at the same relative path under ``<capture>/transcripts/``.
  3. Advances a per-file line watermark in
     ``<capture>/state/sweep-watermarks.json`` — but only after the append
     succeeds, so an interrupted append is retried, never skipped.

Invariants:
  - **Append-only destination.** A source file deleted by Claude Code's ~30-day
    cleanup never deletes its swept copy or its watermark entry.
  - **Idempotent.** Run twice with no source change and the destination tree is
    byte-identical.
  - **Complete lines only.** Partial trailing lines are never copied until the
    newline arrives.
  - Honors ``CAPTURE_DISABLED=1`` (no-op, exit 0).
  - ``--stats`` reports ``files=<n> new_lines=<n>`` and writes nothing.
  - Writes only under ``<capture>/transcripts/`` and ``<capture>/state/``.

No own timer: the backup runner (task 06) invokes this; manual invocation works
too. Source root overridable via ``--source``; capture root via
``CORPUS_CAPTURE_DIR`` (both used by tests).

Runs as a plain file (invoked by absolute path), so it bootstraps its own
package directory onto ``sys.path`` before importing sibling modules.
"""

import argparse
import json
import os
import sys

# --- sys.path bootstrap: make `corpus_capture` importable when run as a file.
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))  # .../corpus_capture
_PKG_ROOT = os.path.dirname(_PKG_DIR)  # package root containing corpus_capture/
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from corpus_capture.redact import redact  # noqa: E402
from corpus_capture.store import capture_dir  # noqa: E402

DEFAULT_SOURCE = os.path.expanduser("~/.claude/projects")

TRANSCRIPTS_SUBDIR = "transcripts"
STATE_SUBDIR = "state"
WATERMARKS_NAME = "sweep-watermarks.json"


def _iter_transcripts(source_root):
    """Yield (relpath, abspath) for every *.jsonl under the source root.

    relpath is POSIX-relative to source_root; it is both the watermark key and
    the mirror-destination path, so the mirror mirrors the source layout exactly
    (including subagent agent-*.jsonl files, which are ordinary *.jsonl).
    """
    if not os.path.isdir(source_root):
        return
    for dirpath, _dirs, files in os.walk(source_root):
        for name in sorted(files):
            if not name.endswith(".jsonl"):
                continue
            abspath = os.path.join(dirpath, name)
            relpath = os.path.relpath(abspath, source_root)
            yield relpath, abspath


def _complete_lines(abspath):
    """Return the list of complete lines (without newlines) in a file.

    Only content up to the last ``\\n`` is considered; a trailing partial line
    (no newline yet) is excluded so a mid-write session is never half-copied.
    """
    try:
        with open(abspath, encoding="utf-8", errors="replace") as fh:
            data = fh.read()
    except OSError:
        return []
    if "\n" not in data:
        return []
    complete = data[: data.rfind("\n") + 1]
    # splitlines() drops the trailing empty element; each element is one line.
    return complete.split("\n")[:-1]


def _load_watermarks(state_dir):
    path = os.path.join(state_dir, WATERMARKS_NAME)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_watermarks(state_dir, watermarks):
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, WATERMARKS_NAME)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(watermarks, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def _append_lines(dest_path, lines):
    """Append redacted lines (each terminated with a newline) to a mirror file."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    payload = "".join(redact(line)[0] + "\n" for line in lines)
    data = payload.encode("utf-8")
    fd = os.open(dest_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def sweep(source_root, cap_dir, stats_only=False):
    """Perform one sweep pass; return (files_seen, new_lines_copied).

    When ``stats_only`` is True, nothing is written: it reports what a real
    sweep would copy given the current watermarks on disk.
    """
    state_dir = os.path.join(cap_dir, STATE_SUBDIR)
    transcripts_dir = os.path.join(cap_dir, TRANSCRIPTS_SUBDIR)
    watermarks = _load_watermarks(state_dir)

    files_seen = 0
    new_lines = 0

    for relpath, abspath in _iter_transcripts(source_root):
        files_seen += 1
        lines = _complete_lines(abspath)
        mark = watermarks.get(relpath, 0)
        # Guard against a truncated/rewritten source shrinking below the mark:
        # never re-copy and never rewind the watermark (append-only).
        if mark > len(lines):
            continue
        fresh = lines[mark:]
        if not fresh:
            continue
        new_lines += len(fresh)
        if stats_only:
            continue
        dest_path = os.path.join(transcripts_dir, relpath)
        _append_lines(dest_path, fresh)
        # Advance the watermark only after a successful append.
        watermarks[relpath] = len(lines)

    if not stats_only and new_lines:
        _save_watermarks(state_dir, watermarks)

    return files_seen, new_lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Sweep Claude Code transcripts.")
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument(
        "--stats",
        action="store_true",
        help="report files seen / new lines without writing anything",
    )
    args = parser.parse_args(argv)

    if os.environ.get("CAPTURE_DISABLED") == "1":
        return 0

    source_root = os.path.expanduser(args.source)
    files_seen, new_lines = sweep(source_root, capture_dir(), stats_only=args.stats)

    if args.stats:
        print(f"files={files_seen} new_lines={new_lines}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
