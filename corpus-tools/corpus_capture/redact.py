"""Redaction engine (full).

The one irreversible transform in the corpus pipeline, and therefore the most
trusted and most thoroughly tested code in it. Every call site — the capture
hook today, Sweep and the Alfred export later — feeds text through ``redact``
and gets back text with every secret replaced by a stable marker plus a
counts-not-contents report. Classification is **local only**; nothing here ever
touches the network.

Secret classes, applied most-specific first so a broad rule can never shadow a
precise one:

  1. pem-block      — a whole ``-----BEGIN … PRIVATE KEY-----`` … ``-----END …-----``
                      block (multi-line) collapses to a SINGLE marker.
  2. bearer-header  — ``Authorization: Bearer <token>`` / ``Authorization: Basic
                      <b64>``; the ``Authorization: Bearer`` / ``Basic`` literal
                      is kept, only the credential is redacted.
  3. api-key        — bare tokens with a known vendor prefix (sk-ant-, sk-,
                      ghp_, gho_, ghs_, github_pat_, AIza, xox[bapr]-, AKIA).
  4. token          — JWT triplets ``eyJ….….…`` (three base64url segments).
  5. env-assignment — ``NAME=value`` where NAME contains SECRET/TOKEN/KEY/
                      PASSWORD/PASSPHRASE; only the value is redacted.
  6. entropy        — fallback: a candidate token >=20 chars whose Shannon
                      entropy exceeds a threshold, EXCEPT 40-hex git SHAs,
                      uuid4s, pure-hex strings and existing ``<REDACTED:…>``
                      markers, which always survive.

A redacted span is replaced by a stable marker ``<REDACTED:xx…yy>`` built from
the first two and last two characters of the secret (U+2026 ellipsis between).
The marker is deterministic: the same secret always yields the byte-identical
marker string, in any surrounding text and at any call site — so a pair can be
matched across events without ever exposing the plaintext.

``redact(text) -> (clean_text, {"count": int, "classes": [str, ...]})``

``count`` is the total number of spans redacted; ``classes`` is deduplicated and
**sorted**. Secret contents never appear in the report.

Implementation shape: each class stage scans the text and yields ``(start, end,
class)`` spans over the *original* string. All spans are collected, overlapping
/ contained spans are dropped in stage-priority order, and marker substitution
happens exactly once at the end. Because the very first thing every stage does
is skip regions already covered by a ``<REDACTED:…>`` marker, running ``redact``
over already-redacted text is a guaranteed no-op (idempotent, adds no counts).
"""

import math
import re

ELLIPSIS = "…"  # …

# Class ordering / priority. Lower index wins when spans overlap.
CLASS_ORDER = [
    "pem-block",
    "bearer-header",
    "api-key",
    "token",
    "env-assignment",
    "entropy",
]

# Entropy detector knobs.
_ENTROPY_MIN_LEN = 20
_ENTROPY_MIN_BITS = 3.5  # Shannon bits/char threshold for "looks random".


def _marker(value: str) -> str:
    if len(value) <= 4:
        # Too short to keep any plaintext edges — redact whole span.
        return f"<REDACTED:{ELLIPSIS}>"
    return f"<REDACTED:{value[:2]}{ELLIPSIS}{value[-2:]}>"


# --- existing markers: never re-redact --------------------------------------
_MARKER_RX = re.compile(r"<REDACTED:[^>]*>")


# --- pem-block --------------------------------------------------------------
# One whole PEM private-key block, BEGIN through END, across newlines.
_PEM_RX = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)

# --- bearer-header ----------------------------------------------------------
# Keep the "Authorization: <scheme> " literal, redact only the credential.
_BEARER_RX = re.compile(
    r"(?P<head>Authorization:\s*(?:Bearer|Basic)\s+)(?P<cred>[A-Za-z0-9._\-+/=]+)"
)

# --- api-key prefixes -------------------------------------------------------
# Known vendor token shapes, longest/most-specific alternative first so e.g.
# `sk-ant-` is not shadowed by the shorter `sk-`.
_API_KEY_RX = re.compile(
    r"(?:"
    r"sk-ant-[A-Za-z0-9._\-]+"
    r"|github_pat_[A-Za-z0-9._\-]+"
    r"|ghp_[A-Za-z0-9]+"
    r"|gho_[A-Za-z0-9]+"
    r"|ghs_[A-Za-z0-9]+"
    r"|xox[bapr]-[A-Za-z0-9\-]+"
    r"|sk-[A-Za-z0-9._\-]+"
    r"|AIza[A-Za-z0-9._\-]+"
    r"|AKIA[A-Z0-9]{12,}"
    r")"
)

# --- token: JWT -------------------------------------------------------------
# Three base64url segments separated by dots; first segment starts `eyJ`.
_JWT_RX = re.compile(
    r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"
)

# --- env-assignment ---------------------------------------------------------
# NAME=value where NAME (uppercase word chars) contains a sensitive substring;
# only the value (group 'val') is redacted, the key name stays for context.
_ENV_ASSIGN_RX = re.compile(
    r"\b[A-Z0-9_]*(?:SECRET|TOKEN|KEY|PASSWORD|PASSPHRASE)[A-Z0-9_]*\s*=\s*"
    r"(?P<val>\S+)"
)

# --- entropy candidate tokenizer + exclusions -------------------------------
_CANDIDATE_RX = re.compile(r"[A-Za-z0-9_\-+/=]{%d,}" % _ENTROPY_MIN_LEN)
_GIT_SHA_RX = re.compile(r"^[0-9a-fA-F]{40}$")
_UUID_RX = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_PURE_HEX_RX = re.compile(r"^[0-9a-fA-F]+$")


def _shannon_bits_per_char(s: str) -> float:
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def _entropy_is_secret(token: str) -> bool:
    """True if `token` looks like a high-entropy secret worth redacting."""
    if len(token) < _ENTROPY_MIN_LEN:
        return False
    # Explicit survivors: git SHAs, uuid4, pure hex.
    if _GIT_SHA_RX.match(token):
        return False
    if _UUID_RX.match(token):
        return False
    if _PURE_HEX_RX.match(token):
        return False
    return _shannon_bits_per_char(token) >= _ENTROPY_MIN_BITS


# --- span collection --------------------------------------------------------
# Each stage yields (start, end, class) tuples over the ORIGINAL text.


def _pem_spans(text: str):
    for m in _PEM_RX.finditer(text):
        yield (m.start(), m.end(), "pem-block")


def _bearer_spans(text: str):
    for m in _BEARER_RX.finditer(text):
        yield (m.start("cred"), m.end("cred"), "bearer-header")


def _api_key_spans(text: str):
    for m in _API_KEY_RX.finditer(text):
        yield (m.start(), m.end(), "api-key")


def _token_spans(text: str):
    for m in _JWT_RX.finditer(text):
        yield (m.start(), m.end(), "token")


def _env_spans(text: str):
    for m in _ENV_ASSIGN_RX.finditer(text):
        yield (m.start("val"), m.end("val"), "env-assignment")


def _entropy_spans(text: str):
    for m in _CANDIDATE_RX.finditer(text):
        if _entropy_is_secret(m.group(0)):
            yield (m.start(), m.end(), "entropy")


_STAGES = [
    _pem_spans,
    _bearer_spans,
    _api_key_spans,
    _token_spans,
    _env_spans,
    _entropy_spans,
]


def redact(text: str):
    if not text:
        return text, {"count": 0, "classes": []}

    # Regions already covered by a marker are off-limits to every stage, which
    # is what makes redact idempotent.
    protected = [(m.start(), m.end()) for m in _MARKER_RX.finditer(text)]

    def _in_protected(start: int, end: int) -> bool:
        return any(not (end <= ps or start >= pe) for ps, pe in protected)

    # Collect candidate spans from every stage, in class-priority order.
    candidates: list[tuple[int, int, str]] = []
    for stage in _STAGES:
        for start, end, cls in stage(text):
            if end <= start:
                continue
            if _in_protected(start, end):
                continue
            candidates.append((start, end, cls))

    # Resolve overlaps: earlier stages have priority. Sort by class priority
    # (then by position) and accept a span only if it does not overlap an
    # already-accepted higher-priority span. This guarantees a byte is redacted
    # by at most one class, so nothing is double-redacted.
    priority = {c: i for i, c in enumerate(CLASS_ORDER)}
    candidates.sort(key=lambda s: (priority[s[2]], s[0], -(s[1] - s[0])))

    accepted: list[tuple[int, int, str]] = []
    for start, end, cls in candidates:
        if any(not (end <= a_s or start >= a_e) for a_s, a_e, _ in accepted):
            continue
        accepted.append((start, end, cls))

    if not accepted:
        return text, {"count": 0, "classes": []}

    # Apply substitutions left-to-right on the original text (single pass).
    accepted.sort(key=lambda s: s[0])
    out: list[str] = []
    cursor = 0
    classes: set[str] = set()
    for start, end, cls in accepted:
        out.append(text[cursor:start])
        out.append(_marker(text[start:end]))
        classes.add(cls)
        cursor = end
    out.append(text[cursor:])

    return "".join(out), {"count": len(accepted), "classes": sorted(classes)}
