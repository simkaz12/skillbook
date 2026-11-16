#!/usr/bin/env python3
"""Weekly health report — visibility that catches silent pipeline death in days.

One invocation scans the Corpus (read-only), prints a plain-text report to
stdout, and writes the byte-identical report to
``<capture>/state/last-health.txt``. The report is deliberately dumb and
grep-friendly:

    generated: <UTC ISO-8601 Z>
    events: prompt=<n> command=<n> stop=<n> session_end=<n> label=<n> message=<n> malformed=<n>
    redactions: <n>
    last sweep: <ts | never>
    backup: <last archive ts + count | unavailable (reason)>
    corpus size: <bytes>  backup size: <bytes | n/a>

What each line answers:
  - **events** — per-``event_type`` counts across every day-file (root
    ``<capture>/*.jsonl`` plus ``<capture>/alfred/*.jsonl`` when present).
    ``malformed`` is any line that is not decodable JSON (a truncated write or a
    hand-edit); it is counted, never fatal.
  - **redactions** — the sum of ``payload.redactions.count`` over every valid
    event. A sudden spike marks a redaction-heavy session; a flat zero marks a
    dead engine.
  - **last sweep** — mtime of ``state/sweep-watermarks.json`` (``never`` absent).
  - **backup** — ``borg list --json --last 1`` via ``BORG_PASSCOMMAND``. When the
    repo/mount/remote host is unreachable the line becomes ``backup: unavailable
    (<reason>)`` and the report still succeeds — visibility must never depend on
    the backup being reachable.
  - **corpus size / backup size** — a ``du``-equivalent byte walk of the capture
    dir, and the borg repo's unique size when reachable (``n/a`` otherwise).

Invariants:
  - **Read-only over the corpus.** The only path health ever writes is
    ``state/last-health.txt``.
  - **Never fails.** Every probe degrades to a placeholder; exit is always 0.

Runs as a plain file (invoked by absolute path from a systemd unit), so it
bootstraps its own package directory onto ``sys.path`` before importing sibling
modules.
"""

import datetime
import json
import os
import subprocess
import sys

# --- sys.path bootstrap: make `corpus_capture` importable when run as a file.
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))  # .../corpus_capture
_PKG_ROOT = os.path.dirname(_PKG_DIR)  # package root containing corpus_capture/
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from corpus_capture.store import capture_dir  # noqa: E402

STATE_SUBDIR = "state"
ALFRED_SUBDIR = "alfred"
WATERMARKS_NAME = "sweep-watermarks.json"
REPORT_NAME = "last-health.txt"

# Fixed, ordered column set for the events line. Kept explicit (not derived from
# the data) so a report always has the same shape: a zero column signals "this
# event stopped arriving", which a data-derived column set would silently hide.
EVENT_COLUMNS = ("prompt", "command", "stop", "session_end", "label", "message")

# borg probes are bounded so an unreachable remote host (hung SSH) can't hang the report.
BORG_TIMEOUT_SECONDS = 30


def _utc_now_iso() -> str:
    """UTC ISO-8601 timestamp with a literal 'Z', seconds precision."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def _iter_day_files(cap_dir):
    """Yield absolute paths of every day-file: root ``*.jsonl`` + ``alfred/*.jsonl``.

    Non-recursive by design — day-files live flat in the capture root and (when
    the Alfred pull is wired) flat under ``alfred/``. Transcript mirrors under
    ``transcripts/`` are deliberately excluded: they are Claude Code transcript
    lines, not events, and would poison the per-type counts.
    """
    for base in (cap_dir, os.path.join(cap_dir, ALFRED_SUBDIR)):
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(base, name)
            if os.path.isfile(path):
                yield path


def scan_events(cap_dir):
    """Scan every day-file; return (counts, malformed, redaction_total).

    ``counts`` is a dict over EVENT_COLUMNS (event types outside the fixed set
    are still tallied so the redaction total stays honest, but only the fixed
    columns are rendered). A line that is not decodable JSON increments
    ``malformed`` and is otherwise ignored.
    """
    counts = {col: 0 for col in EVENT_COLUMNS}
    malformed = 0
    redaction_total = 0

    for path in _iter_day_files(cap_dir):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                lines = fh.read().split("\n")
        except OSError:
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except (ValueError, TypeError):
                malformed += 1
                continue
            if not isinstance(event, dict):
                malformed += 1
                continue
            event_type = event.get("event_type")
            if event_type in counts:
                counts[event_type] += 1
            redaction_total += _redaction_count(event)

    return counts, malformed, redaction_total


def _redaction_count(event) -> int:
    """``payload.redactions.count`` as a non-negative int, tolerant of shape drift."""
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return 0
    redactions = payload.get("redactions")
    if not isinstance(redactions, dict):
        return 0
    count = redactions.get("count")
    return count if isinstance(count, int) and count >= 0 else 0


def _last_sweep(cap_dir) -> str:
    """UTC ISO-8601 mtime of the sweep watermarks file, or ``never`` when absent."""
    path = os.path.join(cap_dir, STATE_SUBDIR, WATERMARKS_NAME)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return "never"
    return (
        datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def _corpus_size(cap_dir) -> int:
    """Sum of file sizes under the capture dir (``du``-equivalent). 0 if missing."""
    total = 0
    for dirpath, _dirs, files in os.walk(cap_dir):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                continue
    return total


def _borg(args, timeout=BORG_TIMEOUT_SECONDS):
    """Run a borg subcommand, returning CompletedProcess. Raises on failure.

    ``BORG_PASSCOMMAND`` (set by the systemd unit) is inherited from the
    environment; nothing here injects a passphrase.
    """
    return subprocess.run(
        ["borg", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )


def _probe_backup(repo):
    """Probe the borg repo; return (backup_line, backup_size).

    On any failure — no repo path, borg missing, unmounted, SSH/passphrase
    error — return an ``unavailable (<reason>)`` line and ``None`` size. The
    report itself never raises: visibility outlives the backup.
    """
    if not repo:
        return "backup: unavailable (no CORPUS_BORG_REPO)", None
    try:
        proc = _borg(["list", "--json", "--last", "1", repo])
        data = json.loads(proc.stdout)
        archives = data.get("archives", []) if isinstance(data, dict) else []
        count = len(archives)
        last = archives[-1] if archives else {}
        ts = last.get("start") or last.get("name") or "unknown"
        line = f"backup: {ts} (archives: {count})"
    except FileNotFoundError:
        return "backup: unavailable (borg not on PATH)", None
    except subprocess.TimeoutExpired:
        return "backup: unavailable (borg timed out)", None
    except subprocess.CalledProcessError as exc:
        reason = (exc.stderr or "").strip().splitlines()
        detail = reason[-1] if reason else f"exit {exc.returncode}"
        return f"backup: unavailable ({detail})", None
    except (ValueError, OSError) as exc:
        return f"backup: unavailable ({exc})", None

    return line, _probe_backup_size(repo)


def _probe_backup_size(repo):
    """Borg repo unique size via ``borg info --json``; None on any failure."""
    try:
        proc = _borg(["info", "--json", repo])
        data = json.loads(proc.stdout)
        stats = data.get("cache", {}).get("stats", {})
        size = stats.get("unique_csize")
        return size if isinstance(size, int) else None
    except (subprocess.SubprocessError, FileNotFoundError, ValueError, OSError):
        return None


def build_report(cap_dir, repo, generated=None) -> str:
    """Render the full plain-text report for one capture dir."""
    generated = generated or _utc_now_iso()
    counts, malformed, redactions = scan_events(cap_dir)

    events = " ".join(f"{col}={counts[col]}" for col in EVENT_COLUMNS)
    events += f" malformed={malformed}"

    backup_line, backup_size = _probe_backup(repo)
    size_field = str(backup_size) if backup_size is not None else "n/a"

    lines = [
        f"generated: {generated}",
        f"events: {events}",
        f"redactions: {redactions}",
        f"last sweep: {_last_sweep(cap_dir)}",
        backup_line,
        f"corpus size: {_corpus_size(cap_dir)}  backup size: {size_field}",
    ]
    return "\n".join(lines) + "\n"


def _write_report(cap_dir, report) -> None:
    """Write the report to ``state/last-health.txt`` (health's only write).

    Skips silently when the capture dir does not exist: a genuinely missing
    corpus has nowhere legitimate to persist a report, and creating the tree
    would break the read-only invariant. The report still prints to stdout.
    """
    if not os.path.isdir(cap_dir):
        return
    state_dir = os.path.join(cap_dir, STATE_SUBDIR)
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, REPORT_NAME)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(report)
    os.replace(tmp, path)


def main() -> int:
    cap_dir = capture_dir()
    repo = os.environ.get("CORPUS_BORG_REPO", "")

    report = build_report(cap_dir, repo)
    # Persist first, then print: the atomic file replace is complete before the
    # first byte reaches stdout, so a same-run reader (e.g. the persistence
    # check `diff <(health.py) state/last-health.txt`) sees a consistent file.
    _write_report(cap_dir, report)
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
