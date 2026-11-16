import os
import re
import shutil
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from . import gitops, state
from .errors import Fault


JUNIT_RE = re.compile(r"\.test-results/[\w.\-]+\.xml")
LIST_CAP = 20


@dataclass
class Result:
    tests: dict = field(default_factory=dict)
    units: dict = field(default_factory=dict)
    first_failure: str = ""
    duration: float = 0.0


def parse_junit(path):
    tests = {}
    messages = {}

    for case in ET.parse(path).getroot().iter("testcase"):
        owner = case.get("classname") or case.get("file") or ""
        ident = f"{owner}::{case.get('name')}"
        bad = case.find("failure")
        if bad is None:
            bad = case.find("error")

        if bad is not None:
            status = "fail"
            messages.setdefault(ident, (bad.get("message") or bad.text or "").strip().splitlines()[:1])
        elif case.find("skipped") is not None:
            status = "skip"
        else:
            status = "pass"

        if tests.get(ident) != "fail":
            tests[ident] = status

    return tests, messages


def classify(base_tests, base_units, cur_tests, cur_units):
    new, pre, fixed = [], [], []

    for ident, status in sorted(cur_tests.items()):
        if status != "fail":
            continue
        if base_tests.get(ident) == "fail":
            pre.append(ident)
        else:
            new.append(ident)

    for ident, status in sorted(base_tests.items()):
        if status == "fail" and cur_tests.get(ident) in ("pass", "skip"):
            fixed.append(ident)

    units = {}
    for cmd, status in cur_units.items():
        if status == "pass" and base_units.get(cmd) == "fail":
            units[cmd] = "fixed"
        elif status == "pass":
            units[cmd] = "ok"
        elif base_units.get(cmd) == "fail":
            units[cmd] = "pre-existing"
        else:
            units[cmd] = "new-failure"

    return {"new": new, "pre": pre, "fixed": fixed, "units": units}


def blocking(classes):
    return bool(classes["new"]) or "new-failure" in classes["units"].values()


def listing(items):
    lines = [f"  {item}" for item in items[:LIST_CAP]]
    if len(items) > LIST_CAP:
        lines.append(f"  ... and {len(items) - LIST_CAP} more")
    return lines


def build_report(info, classes, reused=False):
    head = (
        f"{info['repo']}  tree {info['tree_head']}  "
        f"baseline {info['base']}@{info['merge_base'][:7]}  merge-base {info['merge_base'][:7]}"
    )
    lines = [head]

    if reused:
        lines.append("REUSED  unchanged tree, last compare result")

    if classes["new"]:
        lines.append(f"NEW FAILURES ({len(classes['new'])}), blocking")
        lines += listing(classes["new"])

    lines.append(f"PRE-EXISTING ({len(classes['pre'])})")
    lines += listing(classes["pre"])
    fixed_units = sum(1 for state in classes["units"].values() if state == "fixed")
    lines.append(f"FIXED SINCE BASELINE ({len(classes['fixed']) + fixed_units})")

    for cmd, state in classes["units"].items():
        label = {
            "ok": "ok",
            "fixed": "ok (fixed since baseline)",
            "pre-existing": "failed (pre-existing)",
            "new-failure": "FAILED, blocking",
        }[state]
        lines.append(f"UNITS  {cmd[:60]} {label}")

    lines.append("RESULT new-failures" if blocking(classes) else "RESULT clean")

    return "\n".join(lines)


def first_line_of_log(log):
    lines = [line for line in Path(log).read_text(errors="replace").splitlines() if line.strip()]

    return lines[-1][:300] if lines else ""


def junit_problem(rc, tests):
    if not tests:
        return "junit file holds no tests"
    if rc < 0 or rc >= 128:
        return f"runner terminated abnormally (exit {rc})"
    if rc != 0 and "fail" not in tests.values():
        return f"exit {rc} with no failing test in the junit file"

    return None


def execute(section, tree, main, logdir, tag):
    result = Result()
    results_dir = tree / ".test-results"
    shutil.rmtree(results_dir, ignore_errors=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    rel = os.path.relpath(tree, main)
    env = gitops.clean_env()
    started = time.time()

    for index, raw in enumerate(section.full, 1):
        log = logdir / f"{tag}-{index}.log"
        log.write_bytes(b"")
        rc = gitops.run_logged(raw.replace("{dir}", rel), tree, env, log)
        junit = JUNIT_RE.search(raw)

        if junit is None:
            result.units[raw] = "pass" if rc == 0 else "fail"
            if rc != 0 and not result.first_failure:
                result.first_failure = f"{raw[:80]}: {first_line_of_log(log)} (log {log})"
            continue

        path = tree / junit.group(0)
        if not path.exists():
            result.units[raw] = "fail"
            if not result.first_failure:
                result.first_failure = f"{raw[:80]}: no junit file written (log {log})"
            continue

        try:
            tests, messages = parse_junit(path)
        except ET.ParseError as error:
            result.units[raw] = "fail"
            if not result.first_failure:
                result.first_failure = f"{raw[:80]}: junit unreadable ({error}) (log {log})"
            continue

        result.tests.update(tests)

        problem = junit_problem(rc, tests)
        if problem:
            result.units[raw] = "fail"
            if not result.first_failure:
                result.first_failure = f"{raw[:80]}: {problem} (log {log})"
            continue

        if not result.first_failure:
            for ident, text in messages.items():
                result.first_failure = f"{ident}: {' '.join(text)[:300]} (log {log})"
                break

    result.duration = time.time() - started

    return result


def check_tripwire(result):
    total = len(result.tests) + len(result.units)
    failed = sum(1 for s in result.tests.values() if s == "fail")
    failed += sum(1 for s in result.units.values() if s == "fail")

    if total == 0:
        raise Fault("no tests or units were produced; not saving a baseline")
    if failed * 2 > total:
        raise Fault(
            f"tripwire: {failed} of {total} failed, an environment fault; not saved. "
            f"First failure: {result.first_failure}"
        )
