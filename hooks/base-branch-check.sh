#!/usr/bin/env bash
# SessionStart: tell the session whether the repo's base branch is behind origin.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

input="$(cat)"
cwd="$(printf '%s' "$input" | jq -r '.cwd // empty')"
[ -n "$cwd" ] || exit 0

source "$HERE/scope-map.sh"
base="$(base_branch "$cwd")" || exit 0

emit() {
  printf '%s' "$1" \
    | jq -Rs '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:.}}'
  exit 0
}

report="$(timeout 10 bash "$HERE/../scripts/pull-base.sh" --repo "$cwd" --check 2>/dev/null)" || report=""

field() { printf '%s\n' "$report" | awk -v k="$1" '$1 == k { print $2; exit }'; }

behind="$(field behind)"
if [ -z "$behind" ]; then
  emit "Base branch $base: could not fetch origin; run pull-base.sh by hand."
fi

if [ "$behind" -gt 0 ]; then
  emit "Base branch $base: HEAD is behind origin by $behind commits ($(field overlap) dirty files overlap). Run bash ~/.claude/skills/../scripts/pull-base.sh --no-switch before starting work."
fi

emit "Base branch $base: current."
