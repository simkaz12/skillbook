import argparse
import datetime
import os
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path

from . import containers, gitops, junit, runs, spec, state
from .errors import Fault


@dataclass(frozen=True, slots=True)
class Outcome:
    report: str
    exit: int


def tree_for(repo, section):
    if containers.is_docker(section):
        return spec.PROJECTS / repo / ".baseline"

    return state.state_dir(repo) / "tree"


def baseline_tree(arg):
    if arg in (".", "..") or os.sep in arg:
        return Path(arg)

    return spec.PROJECTS / arg


def record_baseline(arg):
    target = spec.resolve_target(baseline_tree(arg))
    sha = gitops.merge_base(target.top, target.spec.base)
    queued = time.time()

    with state.RepoLock(target.repo) as lock:
        return baseline_locked(target, sha, True, lock.waited, queued)


def baseline_locked(target, sha, rebuild, waited, queued):
    store = state.state_dir(target.repo)
    current = state.load_json(state.snapshot_path(target.repo, sha))
    config = state.config_hash(target.spec, target.section)
    reusable = state.matches(current, config)

    if reusable and not rebuild:
        return current
    if reusable and waited and current["created_at"] >= queued:
        return current

    guard_cargo(target.repo)
    gitops.ensure_excludes(target.main)
    tree = tree_for(target.repo, target.section)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    logdir = store / "logs"
    setup_log = logdir / f"baseline-{stamp}-setup.log"
    setup_log.write_bytes(b"")
    containers.ensure_containers(target.section, target.main, setup_log)
    gitops.prepare_tree(target.section, target.main, tree, setup_log, sha)
    result = junit.execute(target.section, tree, target.main, logdir, f"baseline-{stamp}")
    junit.check_tripwire(result)

    snapshot = {
        "repo": target.repo,
        "base": target.spec.base,
        "commit": sha,
        "created_at": time.time(),
        "config": config,
        "tests": result.tests,
        "units": result.units,
        "duration": result.duration,
    }
    state.write_json(state.snapshot_path(target.repo, sha), snapshot)

    return snapshot


def guard_cargo(repo):
    if spec.is_cargo(repo) and gitops.cargo_running():
        raise Fault(f"{repo}: another cargo process is running; refusing to start")


def compare(tree_arg, expected=None):
    target = spec.resolve_target(tree_arg)
    sha = gitops.merge_base(target.top, target.spec.base)
    store = state.state_dir(target.repo)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    containers.ensure_containers(target.section, target.main, store / "logs" / f"compare-{stamp}-containers.log")
    gitops.ensure_excludes(target.main)
    queued = time.time()

    with state.RepoLock(target.repo) as lock:
        snapshot = baseline_locked(target, sha, False, lock.waited, queued)

        return compare_locked(target, sha, store, snapshot, expected)


def locked_key(target, sha, expected):
    if expected is None:
        return gitops.tree_key(target, sha)

    current = gitops.local_merge_base(target.top, target.spec.base)
    key = gitops.tree_key(target, current)
    if (key, current) != (expected.fingerprint, expected.merge_base):
        raise Fault("tree changed before the run started")

    return key


def compare_locked(target, sha, store, snapshot, expected=None):
    key = locked_key(target, sha, expected)
    last = state.load_json(state.last_compare_path(target.repo))

    if last and last["fingerprint"] == key:
        reused = last["report"].replace("\n", "\nREUSED  unchanged tree, last compare result\n", 1)

        return Outcome(containers.with_containers(reused), last["exit"])

    guard_cargo(target.repo)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    result = junit.execute(target.section, target.top, target.main, store / "logs", f"compare-{stamp}")
    classes = junit.classify(snapshot["tests"], snapshot["units"], result.tests, result.units)
    info = {
        "repo": target.repo,
        "tree_head": gitops.git(target.top, "rev-parse", "--short=7", "HEAD"),
        "base": target.spec.base,
        "merge_base": sha,
    }
    report = junit.build_report(info, classes)
    code = 1 if junit.blocking(classes) else 0
    state.write_json(state.last_compare_path(target.repo), {"fingerprint": key, "report": report, "exit": code})

    return Outcome(containers.with_containers(report), code)


def compare_recorded(tree_arg, path):
    """Run compare and leave a terminal run record at path, whatever happens.

    Catches every exception because this is the background process boundary: nothing reads its
    stderr, so a waiting `land` can only learn of a crash from the record.
    """
    record = runs.load_run(path)
    expected = None if record is None else state.RunKey(record.merge_base, record.fingerprint, Path(path))

    try:
        outcome = compare(tree_arg, expected)
    except Exception as error:
        outcome = Outcome(f"ERROR {error}", runs.FAULT_EXIT)

    record = runs.load_run(path)
    if record is not None:
        finished = replace(record, status="done", exit=outcome.exit, report=outcome.report, finished_at=time.time())
        runs.save_run(path, finished)

    return outcome


def baseline_row(baseline):
    tests = len(baseline["tests"])
    units = len(baseline["units"])
    failed = sum(1 for s in baseline["tests"].values() if s == "fail")
    failed += sum(1 for s in baseline["units"].values() if s == "fail")
    count = f"{tests}" + (f" +{units}u" if units else "")
    seconds = int(baseline["duration"])

    return [
        baseline["repo"],
        f"{baseline['base']}@{baseline['commit'][:7]}",
        count,
        str(failed),
        f"{seconds // 60}m{seconds % 60:02d}s",
    ]


def print_table(rows):
    rows = [["repo", "base@commit", "tests", "pre-existing failures", "duration"]] + rows
    widths = [max(len(row[i]) for row in rows) for i in range(5)]

    for row in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip())


def run_baselines(repos):
    rows = []
    failed = False

    for arg in repos or [spec.cwd_repo()]:
        try:
            rows.append(baseline_row(record_baseline(arg)))
        except Fault as error:
            failed = True
            print(f"{arg}: ERROR {error}", file=sys.stderr)
            rows.append([arg, "-", "-", "-", "error"])

    print_table(rows)
    if containers.containers_line():
        print(containers.containers_line())

    return 2 if failed else 0


def run_compare(args):
    outcome = compare_recorded(args.tree, Path(args.record)) if args.record else compare(args.tree)
    print(outcome.report)

    return outcome.exit


def main():
    parser = argparse.ArgumentParser(prog="test-baseline.py")
    sub = parser.add_subparsers(dest="command", required=True)
    base_parser = sub.add_parser("baseline")
    base_parser.add_argument("repos", nargs="*")
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("tree")
    compare_parser.add_argument("--record", help=argparse.SUPPRESS)
    start_parser = sub.add_parser("start")
    start_parser.add_argument("tree")
    start_parser.add_argument(
        "--rerun",
        action="store_true",
        help="ignore a finished or failed run for this tree and compare again instead of reusing the last result",
    )
    for name in ("wait", "status"):
        sub.add_parser(name).add_argument("tree")
    args = parser.parse_args()

    try:
        match args.command:
            case "baseline":
                return run_baselines(args.repos)
            case "compare":
                return run_compare(args)
            case "start":
                return runs.start(args.tree, args.rerun)
            case "wait":
                return runs.wait(args.tree)
            case _:
                return runs.status(args.tree)
    except Fault as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 2
