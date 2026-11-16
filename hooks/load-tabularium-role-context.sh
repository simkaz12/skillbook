#!/usr/bin/env bash
# SubagentStart: inject per-role Tabularium grounding for a dispatched
# sub-agent — the way SessionStart already delivers main's (see
# load-tabularium-context.sh, whose endpoint/scope-mapping/timeout/curl
# shape this script deliberately reuses rather than reinvents; a divergence
# between the two scripts is a bug surface).
#
# Three profiles ship: "reviewer" (spec-reviewer), "builder" (hand-do /
# spec-runner, added by curation block task 14) and "navigator" (hand-ex
# only, added 2026-08-04). Every other
# agent_type — bolt, and anything unlisted — is a silent no-op: no output,
# exit 0. Adding a profile is a new case arm here, not a rewrite.
#
# Rollback is deleting the one SubagentStart entry in settings.json.
set -euo pipefail

ENDPOINT="${TABULARIUM_MCP_ENDPOINT:-http://memory.example.internal:8787/mcp}"  # override only for testing
BUDGET=2200         # raised 800 -> 1400 by curation block task 06, then 1400 -> 2200 by task 11
                    # (owner decision 2026-08-03, applied twice for the same reason): hot_cap is
                    # enforced per (scope, role) at global=8/project=5, and the invariant
                    # "cap_global + cap_scope <= what the smallest consumer budget delivers"
                    # governs this number. 1400 came from a ~98 tokens/atom estimate taken while
                    # the tier held only short atoms; task 11 filled every cap and measured the
                    # real cost -- 13 atoms is up to 1968 tokens (tabularium/reviewer), ~151
                    # tokens/atom, and 8 of 16 (scope, role) cells were skipping 1-5 records at
                    # 1400. 2200 carries ~12% headroom over the measured worst case. Resolved by
                    # raising the budget rather than shrinking the caps, per task 06's rejected
                    # alternative. Main's own SessionStart budget (load-tabularium-context.sh) is
                    # separate at 3000 and does not move -- its decider payload measures 1450.
TIMEOUT=3           # same posture as load-tabularium-context.sh

input="$(cat)"

agent_type="$(printf '%s' "$input" | jq -r '.agent_type // empty')"
case "$agent_type" in
  spec-reviewer) role=reviewer ;;
  hand-do|spec-runner) role=builder ;;
  hand-ex) role=navigator ;;
  *) exit 0 ;;  # unmapped agent_type — silent no-op, never a default payload
                # bolt stays unmapped DELIBERATELY, and is now the only agent
                # navigator's exclusion is for: it is one-hop and fanned out
                # several at a time, so the payload cost lands worst there while
                # static orientation belongs in bolt.md. hand-ex was mapped
                # 2026-08-04 by owner decision, partially reversing task 14 —
                # once 20 atoms were actually tagged navigator they turned out
                # to be dynamic false-positive traps (gitnexus blindspots,
                # browser_snapshot reporting clipped elements as visible, the
                # SSE-frame trap), not the static primer material task 14
                # assumed when nothing was tagged yet.
esac

cwd="$(printf '%s' "$input" | jq -r '.cwd // empty')"
[ -z "$cwd" ] && exit 0

source "$(dirname "${BASH_SOURCE[0]}")/scope-map.sh"
scope="$(path_scope "$cwd")" || exit 0

emit() {
  printf 'Tabularium grounding (role=%s, scope=%s):\n%s' "$role" "$scope" "$1" \
    | jq -Rs '{hookSpecificOutput:{hookEventName:"SubagentStart",additionalContext:.}}'
  exit 0
}

# A dead memory host must be VISIBLE, never silent, once a role IS mapped — an empty
# block is indistinguishable from "nothing was curated for this role yet".
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

args="{\"scope\":\"$scope\",\"budget\":$BUDGET,\"role\":\"$role\"}"

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
  | if ($lines | length) == 0 then "  (no hot or ember records curated for this role yet)"
    else ($lines | join("\n")) end
' 2>/dev/null || true)"
[ -z "$rendered" ] && fail "could not render payload"

skipped="$(printf '%s' "$text" | jq -r '[.tiers[].skipped] | add // 0' 2>/dev/null || echo 0)"
# A dropped always-on record is not always-on; surface it rather than let the
# budget silently truncate curation.
[ "$skipped" != "0" ] && rendered="$rendered
  [!] $skipped record(s) skipped for budget — raise BUDGET in this hook]"

# Deliberately NOT mirrored from load-tabularium-context.sh (2026-08-11, task 09
# follow-up): that hook appends a last-Cleaner-pass summary here (task 08's
# ContextPayload.cleaner). Its owner_attention items — unclear verdicts,
# global/Decision contradictions, batch failures — are addressed to the OWNER
# (engine/report.py's CleanerReport docstring: "need the owner rather than the
# panel"). A dispatched sub-agent has no authority to act on them and no use for
# them, and this hook's BUDGET is already measured tight per role/scope cell
# (see the BUDGET comment above) — this is the one sanctioned exception to the
# header's "divergence between the two scripts is a bug surface" invariant,
# which otherwise still applies (endpoint/scope-mapping/timeout/curl shape).

emit "$rendered"
