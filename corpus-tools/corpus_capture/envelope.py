"""Envelope builder: wraps a payload in the pinned event envelope.

Pinned envelope contract (v1):
    v            int    always 1
    event_uuid   str    uuid4
    source       str    e.g. "claude-code"
    event_type   str    one of KNOWN_EVENT_TYPES
    ts           str    UTC ISO-8601, seconds precision, "Z" suffix
    hostname     str    socket.gethostname()
    payload      dict   caller-supplied body
"""

import datetime
import socket
import uuid

ENVELOPE_VERSION = 1

# Known event types. Unknown types raise ValueError so a typo at a call site
# fails loud rather than writing an unclassifiable line to the corpus.
#   prompt       — UserPromptSubmit, full enrichment (task 01)
#   stop         — Stop marker, identity-only (task 03)
#   session_end  — SessionEnd marker, identity-only + reason (task 03)
#   message      — Alfred (Hermes) message export, one row per Hermes message (task 09)
#   label        — /flag//good via UserPromptExpansion, blocking (task 04)
#   command      — any slash command via UserPromptExpansion, non-blocking (task 04)
KNOWN_EVENT_TYPES = frozenset(
    {"prompt", "stop", "session_end", "message", "label", "command"}
)


def _utc_now_iso() -> str:
    """UTC ISO-8601 timestamp with a literal 'Z', seconds precision."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_envelope(source: str, event_type: str, payload: dict) -> dict:
    if event_type not in KNOWN_EVENT_TYPES:
        raise ValueError(
            f"unknown event_type {event_type!r}; "
            f"known: {sorted(KNOWN_EVENT_TYPES)}"
        )
    return {
        "v": ENVELOPE_VERSION,
        "event_uuid": str(uuid.uuid4()),
        "source": source,
        "event_type": event_type,
        "ts": _utc_now_iso(),
        "hostname": socket.gethostname(),
        "payload": payload,
    }
