#!/usr/bin/env bash
# SessionStart: inject Tabularium grounding (hot + ember tiers) for the cwd's scope.
#
# Standalone by design — the sole grounding hook since the pi-memory ledger was
# removed 2026-08-20. Renders the FULL payload, not a summary.
set -euo pipefail

ENDPOINT="${TABULARIUM_MCP_ENDPOINT:-http://memory.example.internal:8787/mcp}"  # override only for testing
BUDGET=3000
TIMEOUT=3          # measured median 0.14s post-20c6f0b; 3s is ~20x headroom
ROLE="decider"      # main's role — REQUIRED on context() as of curation block
                    # task 07 (2026-08-03): "default" is retired and an
                    # omitted role now raises rather than resolving to a
                    # fallback, so this must always be a real, registered
                    # role name, never empty. A record reaches this payload
                    # only when "decider" is named in its audience_hint
                    # (explicit enumeration only, task 05) — an untagged
                    # record reaches nobody, this role included.

input="$(cat)"
cwd="$(printf '%s' "$input" | jq -r '.cwd // empty')"
[ -z "$cwd" ] && exit 0

source "$(dirname "${BASH_SOURCE[0]}")/scope-map.sh"
scope="$(path_scope "$cwd")" || exit 0

emit() {
  printf 'Tabularium grounding (%s):\n%s' "$scope" "$1" \
    | jq -Rs '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:.}}'
  exit 0
}

# A dead memory host must be VISIBLE, never silent — an empty block is indistinguishable
# from "nothing was curated", which is the failure that would let the store rot
# unnoticed once this is the only grounding.
fail() { emit "  [unavailable: $1]"; }

# 2026-07-28 modern per-request-envelope path (mcp 2.0.0's
# _streamable_http_modern.py): one self-contained POST, no `initialize`
# handshake, no `Mcp-Session-Id` — the classifier routes on `MCP-Protocol-Version`
# alone, ahead of and independent of the server's stateless_http flag. Every
# modern request carries its own envelope twice: the protocol version and an
# (empty, but present) client-capabilities object travel both as headers
# (routing, checked pre-dispatch) and inside params._meta (payload, checked by
# the same ladder) and must agree; tools/call additionally mirrors its method
# and tool name onto Mcp-Method/Mcp-Name. All four header values are static
# for this one call, so they're hardcoded rather than computed.
PROTO='2026-07-28'
H="-H Content-Type:application/json -H Accept:application/json,text/event-stream -H MCP-Protocol-Version:$PROTO -H Mcp-Method:tools/call -H Mcp-Name:context"
META="{\"io.modelcontextprotocol/protocolVersion\":\"$PROTO\",\"io.modelcontextprotocol/clientCapabilities\":{}}"

args="{\"scope\":\"$scope\",\"budget\":$BUDGET"
[ -n "$ROLE" ] && args="$args,\"role\":\"$ROLE\""
args="$args}"

raw="$(curl -s -X POST "$ENDPOINT" $H --max-time "$TIMEOUT" 2>/dev/null \
  -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"context\",\"arguments\":$args,\"_meta\":$META}}")" \
  || fail "context call failed (memory host unreachable?)"

# Responses are SSE-framed ("event: message" / "data: {...}") only when the
# handler emits a notification before completing; a fast tool call like this
# one lands as plain JSON instead (empirically confirmed against the live
# server). Take the last data: line if present; fall back to the body itself.
resp="$(printf '%s' "$raw" | sed -n 's/^data: //p' | tail -1)"
[ -z "$resp" ] && resp="$raw"

err="$(printf '%s' "$resp" | jq -r '.error.message // empty' 2>/dev/null || true)"
[ -n "$err" ] && fail "$err"

# FastMCP tool-level failures don't set the JSON-RPC .error object above —
# they set .result.isError=true and put the message inside
# .result.content[0].text (same shape as a success payload). Check isError
# before trying to parse that text as tiers JSON, or the tool's error message
# gets fed to the tiers jq below, fails to parse, and surfaces as the generic
# "could not render payload" instead of the real fault.
is_err="$(printf '%s' "$resp" | jq -r '.result.isError // false' 2>/dev/null || echo false)"
if [ "$is_err" = "true" ]; then
  tool_err="$(printf '%s' "$resp" | jq -r '.result.content[0].text // "unknown tool error"' 2>/dev/null || echo "unknown tool error")"
  fail "$tool_err"
fi

text="$(printf '%s' "$resp" | jq -r '.result.content[0].text // empty' 2>/dev/null || true)"
[ -z "$text" ] && fail "empty response"

rendered="$(printf '%s' "$text" | jq -r '
  [ .tiers[] as $t | $t.entries[] | "  [\($t.name)/\(.scope)] \(.content)" ] as $lines
  | if ($lines | length) == 0 then "  (no hot or ember records curated for this scope)"
    else ($lines | join("\n")) end
' 2>/dev/null || true)"
[ -z "$rendered" ] && fail "could not render payload"

skipped="$(printf '%s' "$text" | jq -r '[.tiers[].skipped] | add // 0' 2>/dev/null || echo 0)"
# A dropped always-on record is not always-on; surface it rather than let the
# budget silently truncate curation.
[ "$skipped" != "0" ] && rendered="$rendered
  [!] $skipped record(s) skipped for budget — raise BUDGET in this hook]"

# The last Cleaner pass for this scope, if any (task 08's ContextPayload.cleaner
# — same payload, no second tools/call). `.cleaner` is `null` both when the key
# is absent entirely and when the engine sends it explicitly, so this one check
# covers every scope that has never been cleaned without a separate branch.
#
# SessionStart-only by design (2026-08-11, task 09 follow-up): this block is
# deliberately NOT mirrored into load-tabularium-role-context.sh (the
# SubagentStart hook) — see the matching note there, next to its own
# `skipped` block, for why.
cleaner_block="$(printf '%s' "$text" | jq -r '
  if .cleaner == null then empty
  else
    "\n  [cleaner] " + .cleaner.summary_line
    + ( [ .cleaner.owner_attention[] | "\n    - " + . ] | join("") )
  end
' 2>/dev/null || true)"
[ -n "$cleaner_block" ] && rendered="$rendered$cleaner_block"

blocked_block="$(printf '%s' "$text" | jq -r '
  if (.cleaner.blocked_streak // 0) > 0
  then "\n  [!] cleaner blocked or errored on \(.cleaner.blocked_streak) pass(es) in a row, since \(.cleaner.blocked_since // "unknown")"
  else empty end
' 2>/dev/null || true)"
[ -n "$blocked_block" ] && rendered="$rendered$blocked_block"

emit "$rendered"
