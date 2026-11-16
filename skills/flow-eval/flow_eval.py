#!/usr/bin/env python3
"""Offline runner and collector for bounded, blind workflow comparisons."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


TOKEN_FIELDS = (
    "input_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "output_tokens",
)


def fail(message: str) -> None:
    raise SystemExit(f"flow-eval: {message}")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {path}: {error}")
    if not isinstance(value, dict):
        fail(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    if path.exists():
        fail(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")


def case_paths(case: Path) -> dict[str, Path]:
    return {
        "manifest": case / "manifest.json",
        "public": case / "public",
        "private": case / "private",
        "control": case / "control",
        "runs": case / "runs",
    }


def load_case(case: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    paths = case_paths(case)
    manifest = read_json(paths["manifest"])
    if manifest.get("schema") != 1:
        fail("unsupported or missing manifest schema")
    for key in ("source", "limits", "variants"):
        if key not in manifest:
            fail(f"manifest is missing {key}")
    return manifest, paths


def planned_phases(manifest: dict[str, Any], variant: str) -> list[str]:
    phases = manifest["variants"][variant].get("planned_phases")
    if not isinstance(phases, list) or not phases or not all(isinstance(value, str) and value for value in phases):
        fail(f"{variant} needs a non-empty planned_phases list")
    if len(phases) != len(set(phases)):
        fail(f"{variant} planned_phases must be unique")
    return phases


def validate_variants(manifest: dict[str, Any], private: Path) -> dict[str, str]:
    variants = manifest["variants"]
    if set(variants) != {"baseline", "candidate"}:
        fail("manifest variants must be baseline and candidate")
    baseline = variants["baseline"]
    candidate = variants["candidate"]
    for key in ("model", "environment"):
        if baseline.get(key) != candidate.get(key):
            fail(f"baseline and candidate {key} metadata differ")
    planned_phases(manifest, "baseline")
    planned_phases(manifest, "candidate")
    mapping = read_json(private / "variant-map.json")
    if set(mapping) != {"baseline", "candidate"} or len(set(mapping.values())) != 2:
        fail("private variant-map.json must map baseline and candidate to distinct blind ids")
    return {str(key): str(value) for key, value in mapping.items()}


def tree_digest(root: Path) -> str:
    value = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        value.update(path.relative_to(root).as_posix().encode())
        value.update(b"\0")
        value.update(path.read_bytes())
        value.update(b"\0")
    return value.hexdigest()


def init_case(case: Path) -> None:
    if case.exists():
        fail(f"{case} already exists")
    paths = case_paths(case)
    for path in paths.values():
        if path.name != "manifest.json":
            path.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": 1,
        "case_id": "replace-me",
        "source": {
            "repository": "replace-me",
            "revision": "replace-with-pre-change-commit",
            "snapshot_ref": "replace-with-immutable-snapshot-reference",
        },
        "limits": {"run_cap": 2, "timeout_seconds": 900},
        "variants": {
            "baseline": {
                "model": "replace-me",
                "environment": "replace-me",
                "planned_phases": ["recon", "grill", "to-spec", "runner", "reviewer"],
            },
            "candidate": {
                "model": "replace-me",
                "environment": "replace-me",
                "planned_phases": ["recon", "grill", "to-spec", "runner", "reviewer"],
            },
        },
    }
    write_json(paths["manifest"], manifest)
    (paths["public"] / "ticket.md").write_text("# Ticket\n\nReplace with the frozen ticket text.\n")
    (paths["public"] / "owner-answers.md").write_text("# Owner answers\n\nReplace with the fixed grill answers.\n")
    (paths["private"] / "expected.md").write_text("# Expected findings\n\nKeep this out of candidate workspaces.\n")
    (paths["private"] / "quality-checklist.md").write_text(
        "# Quality checklist\n\n- Does it identify the right behavior and change surface?\n- Does it miss a requirement or decision that affects implementation?\n- Are material claims supported?\n- What would need correction or renewed investigation?\n"
    )
    write_json(paths["private"] / "variant-map.json", {"baseline": "arm-a", "candidate": "arm-b"})
    for variant in ("baseline", "candidate"):
        profile = case / "profiles" / variant
        (profile / "skills").mkdir(parents=True)
        (profile / "agents").mkdir()
        write_json(profile / "launch.json", {"argv": []})
    print(case)


def expand(text: str, workspace: Path, output: Path, source: Path | None, inventory: Path | None = None) -> str:
    return text.format(
        workspace=str(workspace),
        public=str(workspace / "public"),
        skills=str(workspace / ".claude" / "skills"),
        output=str(output),
        inventory=str(inventory or output / "sessions.json"),
        source=str(source or ""),
    )


def parse_usage(values: list[str], workspace: Path, output: Path, source: Path | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            fail("--usage must be SESSION=PATH")
        session, raw_path = value.split("=", 1)
        if not session or session in result:
            fail("each --usage session id must appear once")
        path = Path(expand(raw_path, workspace, output, source))
        result[session] = str(path if path.is_absolute() else workspace / path)
    return result


def resolve_path(raw_path: str, base: Path) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else base / path


def is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def parse_session_inventory(path: Path, planned: list[str], profile_sha256: str) -> tuple[dict[str, Any], str | None]:
    try:
        inventory = read_json(path)
    except SystemExit as error:
        return {}, str(error)
    sessions = inventory.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        return {}, "session inventory has no sessions"
    reported_profile = inventory.get("profile_sha256")
    activation = "attested" if reported_profile == profile_sha256 else "unattested" if reported_profile is None else "mismatch"
    result: dict[str, Any] = {}
    for entry in sessions:
        if not isinstance(entry, dict):
            return {}, "session inventory entry is not an object"
        session_id = entry.get("id")
        phases = entry.get("phases")
        usage = entry.get("usage")
        if not isinstance(session_id, str) or not session_id or session_id in result:
            return {}, "session inventory ids must be unique non-empty strings"
        if not isinstance(phases, list) or not phases or not all(isinstance(phase, str) for phase in phases):
            return {}, f"session {session_id} has no valid phases"
        unknown = sorted(set(phases) - set(planned))
        if unknown:
            return {}, f"session {session_id} names unplanned phases: {', '.join(unknown)}"
        if not isinstance(usage, str) or not usage:
            return {}, f"session {session_id} has no usage path"
        result[session_id] = {"phases": phases, "usage": str(resolve_path(usage, path.parent))}
    return result, activation


def parse_artifacts(values: list[str], workspace: Path, output: Path, source: Path | None, inventory: Path | None) -> list[str]:
    if not values:
        fail("at least one --artifact final report is required")
    artifacts: list[str] = []
    for value in values:
        path = resolve_path(expand(value, workspace, output, source, inventory), workspace)
        if not is_inside(path, output):
            fail("--artifact must be inside {output}")
        relative = path.resolve().relative_to(output.resolve()).as_posix()
        if relative in artifacts:
            fail("each --artifact must be distinct")
        artifacts.append(relative)
    return artifacts


def profile_path(case: Path, variant: str) -> Path:
    path = case / "profiles" / variant
    if not (path / "skills").is_dir() or not (path / "agents").is_dir() or not (path / "launch.json").is_file():
        fail(f"profile {variant} needs skills/, agents/, and launch.json")
    return path


def clean_git_source(source: Path, revision: str) -> None:
    if not (source / ".git").exists():
        fail("--source must be a clean git checkout")
    head = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"], capture_output=True, text=True
    )
    if head.returncode or head.stdout.strip() != revision:
        fail("--source HEAD does not match manifest source.revision")
    status = subprocess.run(
        ["git", "-C", str(source), "status", "--porcelain"], capture_output=True, text=True
    )
    if status.returncode or status.stdout.strip():
        fail("--source must have a clean working tree")


def copy_source(source: Path, destination: Path, revision: str) -> None:
    destination.mkdir()
    for command in (
        ["git", "init", "--quiet", str(destination)],
        ["git", "-C", str(destination), "fetch", "--quiet", "--depth", "1", "--no-tags", str(source), revision],
        ["git", "-C", str(destination), "checkout", "--quiet", "--detach", "FETCH_HEAD"],
    ):
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            fail(f"could not create shallow source fixture: {result.stderr.strip()}")


def existing_runs(control: Path) -> list[dict[str, Any]]:
    path = control / "runs.jsonl"
    if not path.exists():
        return []
    values: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if line:
            values.append(json.loads(line))
    return values


def run_command(args: argparse.Namespace) -> None:
    case = Path(args.case).resolve()
    manifest, paths = load_case(case)
    mapping = validate_variants(manifest, paths["private"])
    if args.variant not in mapping:
        fail("--variant must be baseline or candidate")
    planned = planned_phases(manifest, args.variant)
    limit = manifest["limits"]
    cap = min(int(limit["run_cap"]), args.max_runs if args.max_runs is not None else int(limit["run_cap"]))
    if cap < 1:
        fail("run cap must be positive")
    if os.name != "posix":
        fail("run requires POSIX process-group support")
    lock_path = paths["control"] / "run.lock"
    try:
        lock_descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        fail("another run is reserving this case")
    os.close(lock_descriptor)
    try:
        run_command_locked(args, manifest, paths, mapping, planned, cap)
    finally:
        lock_path.unlink(missing_ok=True)


def run_command_locked(
    args: argparse.Namespace,
    manifest: dict[str, Any],
    paths: dict[str, Path],
    mapping: dict[str, str],
    planned: list[str],
    cap: int,
) -> None:
    if len(existing_runs(paths["control"])) >= cap:
        fail(f"run cap reached ({cap})")
    limit = manifest["limits"]
    timeout = min(int(limit["timeout_seconds"]), args.timeout if args.timeout is not None else int(limit["timeout_seconds"]))
    if timeout < 1:
        fail("timeout must be positive")
    run_dir = Path(args.out).resolve()
    if run_dir.exists():
        fail(f"refusing to overwrite existing run directory {run_dir}")
    workspace = run_dir / "workspace"
    output = run_dir / "output"
    workspace.mkdir(parents=True)
    output.mkdir()
    shutil.copytree(paths["public"], workspace / "public")
    profile = profile_path(case=Path(args.case).resolve(), variant=args.variant)
    shutil.copytree(profile / "skills", workspace / ".claude" / "skills")
    shutil.copytree(profile / "agents", workspace / ".claude" / "agents")
    profile_sha256 = tree_digest(profile)
    source: Path | None = None
    if args.source:
        source = Path(args.source).resolve()
        clean_git_source(source, str(manifest["source"]["revision"]))
        copy_source(source, workspace / "source", str(manifest["source"]["revision"]))
        source = workspace / "source"
    manual_usage = parse_usage(args.usage, workspace, output, source)
    inventory_path = None
    if args.session_inventory:
        inventory_path = resolve_path(expand(args.session_inventory, workspace, output, source), workspace)
    artifacts = parse_artifacts(args.artifact, workspace, output, source, inventory_path)
    command = [expand(item, workspace, output, source, inventory_path) for item in args.command]
    if not command:
        launch = read_json(profile / "launch.json")
        configured = launch.get("argv")
        if not isinstance(configured, list) or not all(isinstance(item, str) for item in configured):
            fail(f"profile {args.variant} launch.json needs an argv list")
        command = [expand(item, workspace, output, source, inventory_path) for item in configured]
    if not command:
        fail("command required after -- or in profile launch.json")
    started = time.monotonic()
    timed_out = False
    environment = os.environ.copy()
    environment.update(
        {
            "FLOW_EVAL_PUBLIC": str(workspace / "public"),
            "FLOW_EVAL_SKILLS": str(workspace / ".claude" / "skills"),
            "FLOW_EVAL_OUTPUT": str(output),
            "FLOW_EVAL_SESSION_INVENTORY": str(inventory_path or output / "sessions.json"),
            "FLOW_EVAL_PROFILE_SHA256": profile_sha256,
            "FLOW_EVAL_PLANNED_PHASES": json.dumps(planned),
        }
    )
    process = subprocess.Popen(
        command,
        cwd=workspace,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env=environment,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
    elapsed = time.monotonic() - started
    (run_dir / "stdout.log").write_text(stdout)
    (run_dir / "stderr.log").write_text(stderr)
    sessions = {session: {"phases": [], "usage": path} for session, path in manual_usage.items()}
    inventory_error = None
    profile_activation = "not-reported"
    if inventory_path:
        discovered, profile_activation = parse_session_inventory(inventory_path, planned, profile_sha256)
        if not discovered:
            inventory_error = profile_activation
            profile_activation = "not-reported"
        else:
            duplicate = sorted(set(sessions) & set(discovered))
            if duplicate:
                inventory_error = f"sessions declared twice: {', '.join(duplicate)}"
            else:
                sessions.update(discovered)
    missing_phases = sorted(set(planned) - {phase for session in sessions.values() for phase in session["phases"]})
    record = {
        "schema": 1,
        "case_id": manifest["case_id"],
        "run_dir": str(run_dir),
        "variant": args.variant,
        "blind_id": mapping[args.variant],
        "workspace": str(workspace),
        "output": str(output),
        "source_copied": source is not None,
        "public_fixture_sha256": tree_digest(paths["public"]),
        "profile_sha256": profile_sha256,
        "profile_activation": profile_activation,
        "planned_phases": planned,
        "missing_planned_phases": missing_phases,
        "inventory_error": inventory_error,
        "sessions": sessions,
        "artifacts": artifacts,
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "elapsed_seconds": elapsed,
    }
    write_json(run_dir / "control.json", record)
    append_jsonl(paths["control"] / "runs.jsonl", record)
    print(run_dir)


def read_run(path: Path, case_id: str) -> dict[str, Any]:
    record = read_json(path / "control.json")
    if record.get("case_id") != case_id:
        fail(f"{path} belongs to another case")
    return record


def review_pack(args: argparse.Namespace) -> None:
    case = Path(args.case).resolve()
    manifest, _ = load_case(case)
    out = Path(args.out).resolve()
    if out.exists():
        fail(f"refusing to overwrite {out}")
    records = [read_run(Path(value).resolve(), manifest["case_id"]) for value in args.run]
    if len(records) != 2:
        fail("blind review needs exactly two runs")
    if len({record["variant"] for record in records}) != 2:
        fail("blind review needs one baseline and one candidate run")
    if len({record["public_fixture_sha256"] for record in records}) != 1:
        fail("public fixture changed between variant runs")
    out.mkdir(parents=True)
    entries = []
    for index, record in enumerate(sorted(records, key=lambda item: item["blind_id"]), start=1):
        entry = f"entry-{index:02d}"
        source = Path(record["output"])
        artifacts = []
        for relative in record["artifacts"]:
            artifact = source / relative
            if not is_inside(artifact, source) or not artifact.is_file():
                fail(f"allowlisted artifact is unavailable: {artifact}")
            destination = out / entry / "artifacts" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(artifact, destination)
            artifacts.append(f"{entry}/artifacts/{relative}")
        entries.append({"entry": entry, "artifacts": artifacts})
    template = {
        "review_complete": False,
        "entries": [{"entry": entry["entry"], "quality": "replace-me", "notes": ""} for entry in entries],
    }
    write_json(out / "quality-template.json", template)
    write_json(out / "blind-report.json", {"case_id": manifest["case_id"], "entries": entries})
    print(out)


def find_usage_rows(value: Any) -> list[tuple[str | None, dict[str, Any]]]:
    found: list[tuple[str | None, dict[str, Any]]] = []
    if isinstance(value, dict):
        message = value.get("message")
        if isinstance(message, dict) and isinstance(message.get("usage"), dict):
            found.append((message.get("id"), message["usage"]))
        if isinstance(value.get("usage"), dict):
            message_id = message.get("id") if isinstance(message, dict) else None
            found.append((message_id, value["usage"]))
        for key, child in value.items():
            if key not in {"message", "usage"}:
                found.extend(find_usage_rows(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(find_usage_rows(child))
    return found


def collect_session(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "unknown", "reason": "usage file missing", "totals": None}
    messages: dict[str, dict[str, int]] = {}
    errors: list[str] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"invalid JSONL line {line_number}")
            continue
        for message_id, usage in find_usage_rows(row):
            if not message_id:
                errors.append(f"usage row without message id at line {line_number}")
                continue
            if any(not isinstance(usage.get(field), int) for field in TOKEN_FIELDS):
                errors.append(f"incomplete usage for {message_id} at line {line_number}")
                continue
            previous = messages.setdefault(str(message_id), {field: 0 for field in TOKEN_FIELDS})
            for field in TOKEN_FIELDS:
                previous[field] = max(previous[field], usage[field])
    if errors or not messages:
        reason = "; ".join(errors) if errors else "no usage rows"
        return {"status": "unknown", "reason": reason, "totals": None}
    return {
        "status": "complete",
        "messages": len(messages),
        "totals": {field: sum(row[field] for row in messages.values()) for field in TOKEN_FIELDS},
    }


def ensure_quality(review: Path, quality_path: Path) -> dict[str, Any]:
    template = read_json(review / "quality-template.json")
    quality = read_json(quality_path)
    expected = {entry["entry"] for entry in template["entries"]}
    actual = {entry.get("entry") for entry in quality.get("entries", []) if isinstance(entry, dict)}
    if not quality.get("review_complete") or actual != expected:
        fail("quality record must mark the blind review complete for every entry")
    return quality


def cost_report(args: argparse.Namespace) -> None:
    case = Path(args.case).resolve()
    manifest, _ = load_case(case)
    review = Path(args.review).resolve()
    ensure_quality(review, Path(args.quality).resolve())
    blind = read_json(review / "blind-report.json")
    controls = [read_run(Path(value).resolve(), manifest["case_id"]) for value in args.run]
    if len(controls) != 2 or {control["variant"] for control in controls} != {"baseline", "candidate"}:
        fail("cost report needs one baseline and one candidate run")
    rows = []
    for control in sorted(controls, key=lambda item: item["variant"]):
        sessions: dict[str, Any] = {}
        for session, details in control["sessions"].items():
            sessions[session] = collect_session(Path(details["usage"]))
            sessions[session]["phases"] = details["phases"]
        usage_complete = bool(sessions) and all(item["status"] == "complete" for item in sessions.values())
        phase_complete = not control["missing_planned_phases"] and control["inventory_error"] is None
        totals = None
        if usage_complete:
            totals = {field: sum(item["totals"][field] for item in sessions.values()) for field in TOKEN_FIELDS}
        rows.append(
            {
                "variant": control["variant"],
                "run_status": "timeout" if control["timed_out"] else "completed" if control["exit_code"] == 0 else "nonzero-exit",
                "exit_code": control["exit_code"],
                "elapsed_seconds": control["elapsed_seconds"],
                "usage_status": "complete" if usage_complete else "incomplete",
                "phase_coverage": "complete" if phase_complete else "incomplete",
                "missing_planned_phases": control["missing_planned_phases"],
                "inventory_error": control["inventory_error"],
                "profile_activation": control["profile_activation"],
                "sessions": sessions,
                "token_totals": totals,
            }
        )
    write_json(Path(args.out).resolve(), {"case_id": manifest["case_id"], "review_entries": blind["entries"], "runs": rows})
    print(Path(args.out).resolve())


def demo_worker(args: argparse.Namespace) -> None:
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "result.md").write_text("offline demo artifact\n")
    usage = {
        "type": "assistant",
        "message": {
            "id": "demo-message",
            "usage": {"input_tokens": 10, "cache_read_input_tokens": 2, "cache_creation_input_tokens": 1, "output_tokens": 5},
        },
    }
    (output / "main.jsonl").write_text(json.dumps(usage) + "\n")
    Path(args.inventory).write_text(json.dumps({"profile_sha256": args.profile_sha256, "sessions": [{"id": "main", "phases": ["demo"], "usage": "main.jsonl"}]}))


def demo(args: argparse.Namespace) -> None:
    case = Path(args.case).resolve()
    init_case(case)
    manifest = read_json(case / "manifest.json")
    manifest["case_id"] = "offline-demo"
    manifest["source"] = {"repository": "not-used", "revision": "not-used", "snapshot_ref": "not-used"}
    manifest["limits"] = {"run_cap": 2, "timeout_seconds": 10}
    manifest["variants"] = {
        "baseline": {"model": "offline", "environment": "offline", "planned_phases": ["demo"]},
        "candidate": {"model": "offline", "environment": "offline", "planned_phases": ["demo"]},
    }
    (case / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for variant, name in (("baseline", "one"), ("candidate", "two")):
        run_command(
            argparse.Namespace(
                case=str(case), variant=variant, out=str(case / "runs" / name), source=None,
                usage=[], session_inventory="{output}/sessions.json", artifact=["{output}/result.md"], timeout=None, max_runs=None,
                command=[sys.executable, str(Path(__file__).resolve()), "demo-worker", "--output", "{output}", "--inventory", "{inventory}", "--profile-sha256", tree_digest(case / "profiles" / variant)],
            )
        )
    review = case / "review"
    review_pack(argparse.Namespace(case=str(case), run=[str(case / "runs" / "one"), str(case / "runs" / "two")], out=str(review)))
    quality = read_json(review / "quality-template.json")
    quality["review_complete"] = True
    for entry in quality["entries"]:
        entry["quality"] = "pass"
    (review / "quality.json").write_text(json.dumps(quality, indent=2) + "\n")
    cost_report(
        argparse.Namespace(
            case=str(case), review=str(review), quality=str(review / "quality.json"), out=str(case / "cost.json"),
            run=[str(case / "runs" / "one"), str(case / "runs" / "two")],
        )
    )
    print(case / "cost.json")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="subcommand", required=True)
    init = commands.add_parser("init")
    init.add_argument("case")
    run = commands.add_parser("run")
    run.add_argument("case")
    run.add_argument("--variant", required=True, choices=("baseline", "candidate"))
    run.add_argument("--out", required=True)
    run.add_argument("--source")
    run.add_argument("--usage", action="append", default=[])
    run.add_argument("--session-inventory")
    run.add_argument("--artifact", action="append", default=[])
    run.add_argument("--timeout", type=int)
    run.add_argument("--max-runs", type=int)
    pack = commands.add_parser("review-pack")
    pack.add_argument("case")
    pack.add_argument("--run", action="append", required=True)
    pack.add_argument("--out", required=True)
    cost = commands.add_parser("cost-report")
    cost.add_argument("case")
    cost.add_argument("--review", required=True)
    cost.add_argument("--quality", required=True)
    cost.add_argument("--run", action="append", required=True)
    cost.add_argument("--out", required=True)
    demo_command = commands.add_parser("demo")
    demo_command.add_argument("case")
    worker = commands.add_parser("demo-worker")
    worker.add_argument("--output", required=True)
    worker.add_argument("--inventory", required=True)
    worker.add_argument("--profile-sha256", required=True)
    return result


def main() -> None:
    raw_arguments = sys.argv[1:]
    command: list[str] = []
    if "--" in raw_arguments:
        divider = raw_arguments.index("--")
        command = raw_arguments[divider + 1 :]
        raw_arguments = raw_arguments[:divider]
    args = parser().parse_args(raw_arguments)
    if args.subcommand == "init":
        init_case(Path(args.case).resolve())
    elif args.subcommand == "run":
        args.command = command
        run_command(args)
    elif args.subcommand == "review-pack":
        review_pack(args)
    elif args.subcommand == "cost-report":
        cost_report(args)
    elif args.subcommand == "demo":
        demo(args)
    elif args.subcommand == "demo-worker":
        demo_worker(args)


if __name__ == "__main__":
    main()
