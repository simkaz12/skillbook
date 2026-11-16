#!/usr/bin/env bash
SKILLBOOK="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd -P)" || exit 0

input="$(cat)"
agent="$(printf '%s' "$input" | jq -r '.agent_type // empty' 2>/dev/null)" || exit 0
cwd="$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)" || exit 0
[ -n "$agent" ] && [ -n "$cwd" ] || exit 0

case "$agent" in
  *[!A-Za-z0-9_-]*) exit 0 ;;
esac

source "$SKILLBOOK/hooks/scope-map.sh" 2>/dev/null || exit 0

main="$(main_checkout "$cwd")" || exit 0
repo="$(basename "$main")"
scope="$(path_scope "$main")" || scope="none"

agent_body="$(print_additions "$SKILLBOOK/agent-projects" "/$agent.md" "$cwd" 2>/dev/null)" || agent_body=""
testing_body="$(print_additions "$SKILLBOOK/agent-projects" "/testing.md" "$cwd" 2>/dev/null)" || testing_body=""

[ -n "$agent_body" ] || [ -n "$testing_body" ] || exit 0

body="$agent_body"
if [ -n "$testing_body" ]; then
  body="${body}${body:+$'\n\n'}${testing_body}"
fi

printf 'Project additions (agent=%s, scope=%s, repo=%s):\n%s' "$agent" "$scope" "$repo" "$body" \
  | jq -Rs '{hookSpecificOutput:{hookEventName:"SubagentStart",additionalContext:.}}' 2>/dev/null
exit 0
