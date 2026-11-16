#!/usr/bin/env bash
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLBOOK="$(cd "$HERE/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

export PROJECTS_ROOT="$TMP/root"
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
LIMIT=1500

fail=0
checked=0
largest=0

for testing in "$SKILLBOOK"/agent-projects/*/testing.md; do
  [ -f "$testing" ] || continue
  key="$(basename "$(dirname "$testing")")"
  base_line="$(grep -m1 '^base:' "$testing")"

  if [ -z "$base_line" ]; then
    echo "not ok: $key: testing.md has no base: line"
    fail=1
    continue
  fi

  while IFS= read -r repo; do
    mkdir -p "$PROJECTS_ROOT/$repo"
    git init -q "$PROJECTS_ROOT/$repo"

    for agent_file in "$SKILLBOOK"/agents/*.md; do
      agent="$(basename "$agent_file" .md)"
      payload="$(jq -nc --arg a "$agent" --arg c "$PROJECTS_ROOT/$repo" '{agent_type: $a, cwd: $c}')"
      out="$(printf '%s' "$payload" | bash "$HERE/load-agent-additions.sh")"
      context="$(printf '%s' "$out" | jq -r '.hookSpecificOutput.additionalContext // empty')"
      size="$(printf '%s' "$context" | wc -m)"
      checked=$((checked + 1))

      if ! printf '%s' "$context" | grep -qxF "$base_line"; then
        echo "not ok: $agent in $repo ($key): additionalContext lacks '$base_line'"
        fail=1
      fi

      if [ "$size" -gt "$LIMIT" ]; then
        echo "not ok: $agent in $repo ($key): additionalContext is $size characters, limit $LIMIT"
        fail=1
      fi

      [ "$size" -gt "$largest" ] && largest="$size"
    done
  done < <(grep -o '^\[[^]]*\]' "$testing" | tr -d '[]')
done

if [ "$checked" -eq 0 ]; then
  echo "not ok: no testing.md found"
  fail=1
fi

if [ "$fail" -eq 0 ]; then
  echo "ok: $checked agent/repo contexts carry testing.md, largest $largest of $LIMIT characters"
fi

exit "$fail"
