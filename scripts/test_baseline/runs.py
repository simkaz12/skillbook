import datetime
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

from . import gitops, spec, state
from .errors import Fault


RUN_POLL = 2
REAP_GRACE = 5
REAP_POLL = 0.1
FAULT_EXIT = 2


def load_run(path):
    data = state.load_json(path)
    if data is None:
        return None

    try:
        return state.RunRecord(**data)
    except TypeError:
        return None


def require_run(path):
    record = load_run(path)
    if record is None:
        raise Fault(f"run record {path} is missing or unreadable")

    return record


def save_run(path, record):
    state.write_json(path, asdict(record))


def pid_alive(pid):
    if pid <= 0:
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

    return True


def minutes_since(moment):
    return int((time.time() - moment) // 60)


def run_key(target, sha):
    fp = gitops.tree_key(target, sha)

    return state.RunKey(sha, fp, state.state_dir(target.repo) / "runs" / f"{fp}.json")


def launch(target, run):
    record = state.RunRecord(
        fingerprint=run.fingerprint,
        tree=str(target.top),
        repo=target.repo,
        merge_base=run.merge_base,
        config=state.config_hash(target.spec, target.section),
        started_at=time.time(),
        pid=0,
        status="running",
    )
    save_run(run.path, record)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log = state.state_dir(target.repo) / "logs" / f"run-{run.id}-{stamp}.log"
    shim = Path(__file__).resolve().parents[1] / "test-baseline.py"
    command = [sys.executable, str(shim), "compare", str(target.top), "--record", str(run.path)]

    with open(log, "ab") as handle:
        proc = subprocess.Popen(
            command,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )

    current = load_run(run.path) or record
    if current.status == "running":
        save_run(run.path, replace(current, pid=proc.pid))


def start(tree_arg, rerun=False):
    target = spec.resolve_target(tree_arg)
    gitops.ensure_excludes(target.main)
    run = run_key(target, gitops.merge_base(target.top, target.spec.base))
    existing = load_run(run.path)

    if rerun and existing is not None and existing.status == "done":
        state.last_compare_path(target.repo).unlink(missing_ok=True)
        existing = None

    if existing is not None and failed(existing):
        print(restart_notice(target, run, existing))
    elif existing is not None and existing.status == "done":
        print(f"run {run.id} already finished; use wait")
        return 0
    elif existing is not None and pid_alive(existing.pid):
        print(f"run {run.id} already running")
        return 0

    reap_gone(existing)
    launch(target, run)
    print(f"started run {run.id}  {target.repo}  merge-base {run.merge_base[:7]}")

    return 0


def earlier_run(target, run):
    paths = sorted((state.state_dir(target.repo) / "runs").glob("*.json"))
    records = [load_run(path) for path in paths]
    others = [
        record
        for record in records
        if record is not None and record.tree == str(target.top) and record.fingerprint != run.fingerprint
    ]

    return max(others, key=lambda record: record.started_at, default=None)


def failed(record):
    return record.status == "done" and record.exit == FAULT_EXIT


def gone(record):
    return record.status == "running" and not pid_alive(record.pid)


def restart_notice(target, run, record):
    if record is not None and failed(record):
        reason = record.report.splitlines()[0] if record.report else "no report"

        return f"run {run.id} failed last time ({reason}); starting again"
    if record is not None:
        return f"run {run.id} is not running (process gone); starting a new run"

    earlier = earlier_run(target, run)
    if earlier is not None:
        return f"tree changed since run {earlier.fingerprint[:7]}; starting a new run"

    return "no run for this tree; starting one"


def stopped(run, record):
    return gone(record) and require_run(run.path).status == "running"


def poll_run(run):
    """Poll until the record is done or its process is gone; a gone process returns the running record."""
    record = require_run(run.path)

    while record.status == "running":
        time.sleep(RUN_POLL)
        record = require_run(run.path)
        if stopped(run, record):
            return record

    return record


def signal_group(pid, sig):
    try:
        os.killpg(pid, sig)
    except (ProcessLookupError, PermissionError):
        return False

    return True


def reap_group(record):
    """Terminate the process group of a run that is being replaced, then wait for it to empty.

    The worker is its own session leader, so its pid is the group id and its suite children share it.
    Sends SIGKILL when the group outlives REAP_GRACE seconds of SIGTERM. Never signals pid 0 or the
    caller's own group.
    """
    pid = record.pid
    if pid <= 0 or pid == os.getpgid(0):
        return

    if not signal_group(pid, signal.SIGTERM):
        return

    deadline = time.monotonic() + REAP_GRACE
    while time.monotonic() < deadline:
        if not signal_group(pid, 0):
            return

        time.sleep(REAP_POLL)

    signal_group(pid, signal.SIGKILL)


def reap_gone(record):
    if record is not None and gone(record):
        reap_group(record)


def restart_run(target, run, record):
    print(restart_notice(target, run, record))
    reap_gone(record)
    launch(target, run)

    return require_run(run.path)


def wait(tree_arg):
    target = spec.resolve_target(tree_arg)
    gitops.ensure_excludes(target.main)
    run = run_key(target, gitops.merge_base(target.top, target.spec.base))
    record = load_run(run.path)

    if record is None or gone(record) or failed(record):
        record = restart_run(target, run, record)

    while record.status == "running":
        print(f"waiting for run {run.id} (started {minutes_since(record.started_at)}m ago)")
        record = poll_run(run)
        if record.status == "running":
            record = restart_run(target, run, record)

    print(record.report)

    return record.exit


def run_summary(run):
    record = load_run(run.path)
    if record is None:
        return "none"
    if record.status == "running":
        return f"{run.id} running {minutes_since(record.started_at)}m"

    return f"{run.id} done exit {record.exit}"


def status(tree_arg):
    target = spec.resolve_target(tree_arg)
    sha = gitops.local_merge_base(target.top, target.spec.base)
    run = run_key(target, sha)
    snapshot = "present" if state.snapshot_path(target.repo, sha).exists() else "missing"
    print(f"{target.repo}  merge-base {sha[:7]}  snapshot {snapshot}  run {run_summary(run)}")

    return 0
