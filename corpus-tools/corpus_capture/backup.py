#!/usr/bin/env python3
"""Backup runner — sweep, then archive the capture tree into an append-only borg repo.

One invocation runs, in order:

  1. **mount-guard** — refuse loudly unless ``$CORPUS_BACKUP_MOUNT`` is an active
     mountpoint AND ``$CORPUS_BORG_REPO`` exists. This makes a fake backup
     impossible: if the external disk is not mounted, ``os.path.ismount`` is
     False and the run aborts (exit 2) before writing anything, so an archive
     can never quietly accumulate on the root disk.
  2. **sweep** — task-05's transcript sweep, called in-process (imported), so the
     archive always captures the freshest complete transcript lines.
  3. **Alfred pull** — a plain ``rsync -a`` (archive, no mirror-removal) of the
     remote host's Alfred corpus into ``<capture>/alfred/`` so the small pool inherits
     the big pool's durability without depending on tunnel uptime. The remote host being
     unreachable (relocation, tunnel down, powered off) is not an error: it
     logs exactly one ``alfred pull: skipped (<reason>)`` line and the run
     proceeds to ``borg create``. The pull can never fail the backup, and it
     never removes — a wiped remote host must not wipe the mirror (append-only extends
     to the pull). The remote is overridable via ``$CORPUS_ALFRED_REMOTE``; the
     destination is ``<capture>/alfred/`` (``$CORPUS_CAPTURE_DIR`` reused).
  4. **borg create** — ``borg create --stats ::corpus-<utc> ~/.claude/capture``
     with a UTC-timestamped archive name.

``--check`` runs ``borg check <repo>`` instead (weekly integrity), and does
nothing else. ``--dry-run`` prints the planned step order and the exact borg
command without executing anything.

Append-only is structural: this module only ever adds archives. The archive
name is unique per run, and retention is handled out-of-band, never here. A test
greps this source to enforce that no retention/removal verbs ever appear.

Runs as a plain file (invoked by absolute path from a systemd unit), so it
bootstraps its own package directory onto ``sys.path`` before importing sibling
modules.
"""

import argparse
import datetime
import os
import subprocess
import sys

# --- sys.path bootstrap: make `corpus_capture` importable when run as a file.
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))  # .../corpus_capture
_PKG_ROOT = os.path.dirname(_PKG_DIR)  # package root containing corpus_capture/
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from corpus_capture import sweep as sweep_mod  # noqa: E402
from corpus_capture.store import capture_dir  # noqa: E402

# Guard exit code — distinct from a generic failure so callers/units can tell
# "the disk wasn't mounted" apart from "borg errored".
GUARD_EXIT = 2

# Pinned Alfred-pull remote. The remote hostname (not the LAN IP) so a relocation
# only moves DNS, never this default. Overridable via $CORPUS_ALFRED_REMOTE for
# tests (a local path is a valid rsync source — same code path, no ssh).
DEFAULT_ALFRED_REMOTE = "user@remote-host.example:/home/user/.corpus/alfred/"

# ssh transport with pinned, short timeouts: an unreachable remote host fails fast
# (ConnectTimeout=5) and BatchMode=yes forbids any interactive prompt, so the
# pull can never hang the backup. --timeout=15 bounds a stalled transfer.
_SSH_TRANSPORT = "ssh -o ConnectTimeout=5 -o BatchMode=yes"


def _archive_name(now=None) -> str:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return "corpus-" + now.strftime("%Y-%m-%dT%H-%M-%S")


def _create_command(repo: str, capture: str, now=None) -> list:
    """The exact ``borg create`` command for one archive run."""
    archive = f"{repo}::{_archive_name(now)}"
    return ["borg", "create", "--stats", archive, capture]


def _default_runner(cmd: list) -> int:
    """Run a command, streaming its output; return its exit code."""
    return subprocess.run(cmd).returncode


def _run_sweep() -> None:
    """In-process sweep of Claude Code transcripts into the capture tree."""
    source = os.environ.get("CORPUS_BACKUP_SOURCE") or sweep_mod.DEFAULT_SOURCE
    source = os.path.expanduser(source)
    sweep_mod.sweep(source, capture_dir(), stats_only=False)


def _alfred_remote() -> str:
    """The rsync source for the Alfred pull ($CORPUS_ALFRED_REMOTE or pinned)."""
    return os.environ.get("CORPUS_ALFRED_REMOTE") or DEFAULT_ALFRED_REMOTE


def _alfred_dest(capture: str | None = None) -> str:
    """The rsync destination — ``<capture>/alfred/`` (trailing slash for rsync)."""
    base = capture or capture_dir()
    return os.path.join(base, "alfred") + os.sep


def _pull_command(remote: str, dest: str) -> list:
    """The exact ``rsync`` command for the Alfred pull.

    Plain ``-a`` (archive) so a grown remote day-file updates its local mirror.
    The mirror-removal flag is deliberately absent: a file wiped on the remote host must
    survive locally, so the append-only guarantee extends across the pull.
    Timeouts are pinned so an unreachable remote host fails fast rather than hanging.
    """
    return [
        "rsync",
        "-a",
        "--timeout=15",
        "-e",
        _SSH_TRANSPORT,
        remote,
        dest,
    ]


def _skip_reason(returncode: int, stderr: str) -> str:
    """Condense an rsync failure into a one-line skip reason.

    Prefers rsync's own last stderr line (which names the cause — unreachable
    host, timeout, refused connection); falls back to the exit code.
    """
    for line in reversed(stderr.splitlines()):
        line = line.strip()
        if line:
            return line
    return f"rsync exit {returncode}"


def alfred_pull(
    remote: str | None = None,
    dest: str | None = None,
    runner=None,
) -> int:
    """Best-effort ``rsync`` pull of the remote host's Alfred corpus into ``<dest>``.

    Never fails the backup: on any rsync error (unreachable remote host, timeout,
    refused connection) it logs exactly one ``alfred pull: skipped (<reason>)``
    line and returns 0. A successful pull also returns 0. ``runner`` is
    injectable for tests but defaults to a stderr-capturing subprocess so the
    skip reason carries rsync's own diagnosis.

    The destination directory is created first so rsync into a fresh capture
    tree never fails merely because ``<capture>/alfred/`` did not exist yet.
    """
    remote = remote or _alfred_remote()
    dest = dest or _alfred_dest()
    os.makedirs(dest, exist_ok=True)

    cmd = _pull_command(remote, dest)

    if runner is not None:
        # Injected runner returns just the exit code; no stderr to mine.
        rc = runner(cmd)
        if rc != 0:
            print(f"alfred pull: skipped (rsync exit {rc})")
        return 0

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"alfred pull: skipped ({_skip_reason(proc.returncode, proc.stderr)})")
    return 0


def _guard(mount: str, repo: str, assume_mounted: bool) -> str | None:
    """Return an error message if the run must be refused, else None.

    Refuse unless the mount is an active mountpoint AND the repo dir exists.
    ``assume_mounted`` bypasses only the mountpoint check (test-only); the repo
    existence check always holds.
    """
    if not assume_mounted and not os.path.ismount(mount):
        return f"refusing: {mount} is not a mountpoint"
    if not os.path.isdir(repo):
        return f"refusing: borg repo {repo} does not exist"
    return None


def run_backup(
    mount: str,
    repo: str,
    capture: str,
    assume_mounted: bool = False,
    runner=None,
    sweep_fn=None,
    pull_fn=None,
    now=None,
) -> int:
    """Sweep, pull (best-effort), then archive — the real backup pipeline.

    ``runner`` runs the borg command (injectable for tests); ``sweep_fn`` and
    ``pull_fn`` default to the in-process implementations. Returns 0 on success,
    non-zero on a fatal step (guard refusal or a sweep/borg error).
    """
    runner = runner or _default_runner
    sweep_fn = sweep_fn or _run_sweep
    pull_fn = pull_fn or (lambda: alfred_pull(dest=_alfred_dest(capture)))

    err = _guard(mount, repo, assume_mounted)
    if err:
        print(err, file=sys.stderr)
        return GUARD_EXIT

    # Sweep first. A sweep failure aborts before borg create so we never archive
    # an unswept corpus mid-error.
    try:
        sweep_fn()
    except Exception as exc:  # noqa: BLE001 — abort the run, report the reason.
        print(f"sweep failed, aborting backup: {exc}", file=sys.stderr)
        return 1

    # Alfred pull is best-effort: a failure here is logged and the run continues.
    try:
        pull_fn()
    except Exception as exc:  # noqa: BLE001 — non-fatal, keep going.
        print(f"alfred pull failed (continuing): {exc}", file=sys.stderr)

    return runner(_create_command(repo, capture, now=now))


def run_check(
    mount: str,
    repo: str,
    assume_mounted: bool = False,
    runner=None,
) -> int:
    """``borg check <repo>`` and nothing else (weekly integrity pass)."""
    runner = runner or _default_runner

    err = _guard(mount, repo, assume_mounted)
    if err:
        print(err, file=sys.stderr)
        return GUARD_EXIT

    return runner(["borg", "check", repo])


def _dry_run(repo: str, capture: str) -> int:
    """Print the planned step order without executing anything."""
    print("sweep")
    pull_cmd = _pull_command(_alfred_remote(), _alfred_dest(capture))
    print("alfred-pull " + " ".join(pull_cmd))
    print(" ".join(_create_command(repo, capture)))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Corpus backup runner (borg).")
    parser.add_argument(
        "--check",
        action="store_true",
        help="run `borg check <repo>` instead of creating an archive",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the planned steps and the exact borg command; run nothing",
    )
    parser.add_argument(
        "--assume-mounted",
        action="store_true",
        help="skip the mountpoint check (test-only guard bypass)",
    )
    args = parser.parse_args(argv)

    mount = os.environ.get("CORPUS_BACKUP_MOUNT", "")
    repo = os.environ.get("CORPUS_BORG_REPO", "")
    # capture_dir() honors CORPUS_CAPTURE_DIR and falls back to ~/.claude/capture,
    # so the swept tree and the archived path are always the same directory.
    capture = capture_dir()

    if args.dry_run:
        # Dry-run is a pure plan preview that executes nothing. With
        # --assume-mounted (the documented preview/test path) the guard is
        # skipped entirely, so the three planned steps always print. Without it,
        # a real mount is still required so the preview never lies about a run
        # that could not happen.
        if not args.assume_mounted:
            err = _guard(mount, repo, args.assume_mounted)
            if err:
                print(err, file=sys.stderr)
                return GUARD_EXIT
        return _dry_run(repo, capture)

    if args.check:
        return run_check(mount, repo, assume_mounted=args.assume_mounted)

    return run_backup(mount, repo, capture, assume_mounted=args.assume_mounted)


if __name__ == "__main__":
    sys.exit(main())
