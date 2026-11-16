#!/usr/bin/env python3
"""Claude Code capture entry point.

Hook events: UserPromptSubmit / Stop / SessionEnd / UserPromptExpansion.

Pinned entry-point contract:
    stdin JSON
      -> CAPTURE_DISABLED check (env == "1" -> nothing written; label mode
         still emits the block decision — a label keystroke must never
         accidentally become a model turn)
      -> enrich BY EVENT TYPE:
           prompt              -> full enrich (redacted prompt + git best-effort)
           stop / session_end  -> identity-only passthrough (no prompt text, no
                                  transcript content, no git — markers must be
                                  instant)
           label               -> identity + label + optional redacted reason;
                                  stdout a block decision (with an
                                  operator-facing `reason`) unconditionally
           command             -> identity + command + redacted args;
                                  non-blocking (stdout stays empty)
      -> append exactly one envelope line to today's day-file
      -> exit 0 unconditionally; errors are owned by the capture log.

Live stdin field names (verified against
https://docs.claude.com/en/docs/claude-code/hooks on 2026-07-11):
  - UserPromptSubmit: `session_id`, `transcript_path`, `cwd`, `prompt`
    (plus `hook_event_name`). Only the first four are mapped.
  - Stop: common fields `session_id`, `transcript_path`, `cwd`
    (plus `hook_event_name`, `stop_hook_active`, `last_assistant_message`,
    `background_tasks`, `session_crons` — all ignored by the marker path).
  - SessionEnd: common fields `session_id`, `transcript_path`, `cwd`
    (plus `hook_event_name`) and a `reason` field (one of `clear`, `resume`,
    `logout`, `prompt_input_exit`, `bypass_permissions_disabled`, `other`).
    Only `session_id`, `cwd`, `transcript_path`, `reason` are mapped.
  - UserPromptExpansion (probe-captured live 2026-07-12, fixtures under
    tests/fixtures/upe-*.json): common fields `session_id`,
    `transcript_path`, `cwd` plus `permission_mode`, `hook_event_name`
    ("UserPromptExpansion"), `expansion_type` ("slash_command"),
    `command_name`, `command_args` (empty string when the command is bare,
    never absent), `command_source`, `prompt` (raw typed text). Only
    `session_id`, `cwd`, `command_name`, `command_args` are mapped; built-in
    CLI commands (e.g. /model) never reach this event.

The script is designed to run as a plain file (the installed hook invokes it by
absolute path), so it bootstraps its own package directory onto sys.path before
importing sibling modules.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import traceback

# --- sys.path bootstrap: make `corpus_capture` importable when run as a file.
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))  # .../corpus_capture
_PKG_ROOT = os.path.dirname(_PKG_DIR)  # package root containing corpus_capture/
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from corpus_capture.envelope import build_envelope  # noqa: E402
from corpus_capture.redact import redact  # noqa: E402
from corpus_capture.store import append_event  # noqa: E402

DEFAULT_LOG = os.path.expanduser("~/.claude/corpus-tools/capture.log")

# Guardrail: refuse absurdly large stdin so a runaway paste can't blow memory.
MAX_STDIN_BYTES = 5 * 1024 * 1024  # 5 MiB


def _log_path() -> str:
    return os.environ.get("CORPUS_CAPTURE_LOG") or DEFAULT_LOG


def _log_error(msg: str) -> None:
    """Best-effort single-line error append to the capture log."""
    try:
        path = _log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        ts = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{ts} {msg}\n")
    except Exception:
        # The log is the last line of defense; if even it fails, stay silent.
        pass


def _git_info(cwd: str):
    """Best-effort {branch, head} for a git-repo cwd; None otherwise.

    Every subprocess is bounded to <=1s. Any failure (not a repo, git missing,
    timeout) returns None so the caller omits the `git` key entirely.
    """
    if not cwd or not os.path.isdir(cwd):
        return None

    def _git(args):
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=1,
        )

    try:
        inside = _git(["rev-parse", "--is-inside-work-tree"])
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return None
        branch = _git(["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
        head = _git(["rev-parse", "HEAD"]).stdout.strip()
        if not head:
            return None
        info = {"head": head}
        if branch:
            info["branch"] = branch
        return info
    except Exception:
        return None


# Marker events carry session identity only — no content, no enrichment.
MARKER_EVENT_TYPES = frozenset({"stop", "session_end"})


def _build_prompt_payload(data: dict):
    prompt = data.get("prompt", "")
    if not isinstance(prompt, str):
        prompt = str(prompt)

    clean, redactions = redact(prompt)

    payload = {
        "prompt": clean,
        "redactions": redactions,
        "session_id": data.get("session_id"),
        "cwd": data.get("cwd"),
    }

    transcript = data.get("transcript_path")
    if transcript:
        payload["transcript_path"] = transcript

    git = _git_info(data.get("cwd", ""))
    if git is not None:
        payload["git"] = git

    return payload


def _build_marker_payload(data: dict, event_type: str):
    """Identity-only payload for Stop / SessionEnd markers.

    No prompt text, no transcript content, no git enrichment — markers must be
    instant. ``redactions`` is the empty report so every event line carries a
    uniform shape. Only ``session_end`` passes through ``reason``.
    """
    # Nothing to scrub, but keep the report shape uniform across event types.
    _, redactions = redact("")

    payload = {
        "session_id": data.get("session_id"),
        "cwd": data.get("cwd"),
        "redactions": redactions,
    }

    transcript = data.get("transcript_path")
    if transcript:
        payload["transcript_path"] = transcript

    if event_type == "session_end":
        reason = data.get("reason")
        if reason:
            payload["reason"] = reason

    return payload


def _command_args_text(data: dict) -> str:
    args_text = data.get("command_args", "")
    if not isinstance(args_text, str):
        args_text = str(args_text)
    return args_text


def _build_label_payload(data: dict):
    """Dumb label: identity + label + optional redacted reason.

    No pairing, no interpretation, no prompt text — pairing with the
    preceding exchange is compile-time. `reason` is present only when
    `/flag <reason>` carried args.
    """
    reason, redactions = redact(_command_args_text(data))

    payload = {
        "session_id": data.get("session_id"),
        "cwd": data.get("cwd"),
        "label": data.get("command_name"),
        "redactions": redactions,
    }
    if reason:
        payload["reason"] = reason
    return payload


def _build_command_payload(data: dict):
    """Slash-command visibility: identity + command + redacted args."""
    clean_args, redactions = redact(_command_args_text(data))

    return {
        "command": data.get("command_name"),
        "args": clean_args,
        "session_id": data.get("session_id"),
        "cwd": data.get("cwd"),
        "redactions": redactions,
    }


def _build_payload(data: dict, event_type: str):
    if event_type in MARKER_EVENT_TYPES:
        return _build_marker_payload(data, event_type)
    if event_type == "label":
        return _build_label_payload(data)
    if event_type == "command":
        return _build_command_payload(data)
    return _build_prompt_payload(data)


def _label_block_decision(outcome: str, label_name):
    """Block decision for a label keystroke, carrying an operator-facing reason.

    The label path is invisible — it never reaches the model — so this block
    message is the ONLY feedback the operator gets. Make a successful capture
    read obviously different from a silent miss:
      - ``captured`` -> confirmation the event landed in the corpus
      - ``disabled`` -> kill-switch notice (nothing recorded, by design)
      - ``failed``   -> pointer to the capture log

    Every branch still blocks the turn: a label keystroke must never become a
    model turn, even when the append was skipped or failed.
    """
    label = label_name or "label"
    if outcome == "captured":
        reason = f"✓ {label} captured to corpus — no model turn"
    elif outcome == "disabled":
        reason = (
            "⚠ capture disabled (CAPTURE_DISABLED=1) — label not recorded, "
            "no model turn"
        )
    else:  # failed
        reason = (
            f"⚠ {label} capture FAILED — see "
            "~/.claude/corpus-tools/capture.log (blocked anyway, no model turn)"
        )
    return {"decision": "block", "reason": reason}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-type", required=True)
    args = parser.parse_args(argv)

    # Track the label outcome so the block decision can carry an honest,
    # user-facing confirmation. Pessimistic default: only a completed append
    # proves the event actually landed in the corpus.
    outcome = "failed"
    label_name = None
    try:
        if os.environ.get("CAPTURE_DISABLED") == "1":
            outcome = "disabled"
        else:
            raw = sys.stdin.buffer.read(MAX_STDIN_BYTES + 1)
            if len(raw) > MAX_STDIN_BYTES:
                raise ValueError("stdin exceeds MAX_STDIN_BYTES")
            if not raw.strip():
                raise ValueError("empty stdin")

            # strict=False tolerates literal control characters (e.g. a real
            # newline inside a multi-line prompt paste) inside JSON strings;
            # the hook then redacts and stores the multi-line prompt as-is.
            data = json.loads(raw.decode("utf-8"), strict=False)
            if not isinstance(data, dict):
                raise ValueError("stdin JSON is not an object")

            payload = _build_payload(data, args.event_type)
            envelope = build_envelope("claude-code", args.event_type, payload)
            append_event(envelope)
            if args.event_type == "label":
                label_name = payload.get("label")
            outcome = "captured"
    except Exception as exc:  # noqa: BLE001 — capture must never break the hook.
        _log_error(
            f"capture_hook error: {exc.__class__.__name__}: {exc} | "
            + traceback.format_exc().replace("\n", " ")
        )

    # A label keystroke must never become a model turn: emit the block
    # decision even when the append was skipped (kill switch) or failed. The
    # reason turns the bare "Blocked by hook" into a capture confirmation.
    if args.event_type == "label":
        print(json.dumps(_label_block_decision(outcome, label_name)))

    # Exit 0 unconditionally: a failing capture must never block a prompt.
    return 0


if __name__ == "__main__":
    sys.exit(main())
