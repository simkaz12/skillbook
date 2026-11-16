#!/usr/bin/env bash
set -euo pipefail

SKILLBOOK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SERVERS_FILE="$SKILLBOOK/mcp/servers.json"
TARGET="${CLAUDE_JSON:-$HOME/.claude.json}"
PROJECTS_ROOT="${PROJECTS_ROOT:-$HOME/Projects}"

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run)
      [ "$DRY_RUN" -eq 0 ] || { echo "usage: sync-mcp.sh [--dry-run]" >&2; exit 1; }
      DRY_RUN=1
      ;;
    *)
      echo "usage: sync-mcp.sh [--dry-run]" >&2
      exit 1
      ;;
  esac
done

command -v jq >/dev/null 2>&1 || { echo "error: jq not found on PATH" >&2; exit 1; }
[ -f "$SERVERS_FILE" ] || { echo "error: $SERVERS_FILE missing" >&2; exit 1; }

TMP_FILES=()
cleanup_tmp_files() {
  local f
  for f in "${TMP_FILES[@]:-}"; do
    if [ -n "$f" ] && [ -f "$f" ]; then
      rm -f "$f"
    fi
  done
  return 0
}
trap cleanup_tmp_files EXIT

existing_projects() {
  local name
  while IFS= read -r name; do
    [ -d "$PROJECTS_ROOT/$name" ] && printf '%s\n' "$name"
  done < <(jq -r '.projects | keys[]' "$SERVERS_FILE")
  return 0
}

EXISTING_JSON="$(existing_projects | jq -R . | jq -s .)"

SUBSTITUTED="$(jq -c --arg home "$HOME" --argjson exists "$EXISTING_JSON" '
  def subst: walk(if type == "string" then split("$HOME") | join($home) else . end);
  {
    user: (.user // {} | subst),
    projects: ((.projects // {} | subst) | with_entries(select(.key as $k | $exists | index($k))))
  }
' "$SERVERS_FILE")"

COMMANDS="{}"
while IFS=$'\t' read -r label cmd; do
  [ -n "$cmd" ] || continue
  resolved="$(command -v "$cmd" || true)"
  if [ -z "$resolved" ]; then
    echo "error: $label: $cmd not found on PATH" >&2
    exit 1
  fi
  COMMANDS="$(jq -c --arg c "$cmd" --arg r "$resolved" '. + {($c): $r}' <<<"$COMMANDS")"
done < <(jq -r '
  (.user | to_entries[] | ["user/" + .key, .value] ),
  (.projects | to_entries[] | .key as $p | .value | to_entries[] | [$p + "/" + .key, .value])
  | select(.[1].command? // "" | (length > 0 and (contains("/") | not)))
  | [.[0], .[1].command] | @tsv
' <<<"$SUBSTITUTED")

RENDERED="$(jq -c --argjson cmds "$COMMANDS" '
  def fix: (.command? // "") as $c | if $cmds[$c] != null then .command = $cmds[$c] else . end;
  {
    user: (.user | map_values(fix)),
    projects: (.projects | map_values(map_values(fix)))
  }
' <<<"$SUBSTITUTED")"

if [ -f "$TARGET" ]; then
  CURRENT="$(cat "$TARGET")"
else
  CURRENT="{}"
fi

LISTED_JSON="$(jq -c '.projects // {} | keys' "$SERVERS_FILE")"

RESULT="$(jq -c --argjson want "$RENDERED" --arg root "$PROJECTS_ROOT" \
  --argjson exists "$EXISTING_JSON" --argjson listed "$LISTED_JSON" '
  def diff($scope; $cur; $des):
    [ ($cur | keys[]) as $k | select($des | has($k) | not) | "\($scope): remove \($k)" ]
    + [ ($des | keys[]) as $k | select($cur | has($k) | not) | "\($scope): add \($k)" ]
    + [ ($des | keys[]) as $k | select($cur | has($k)) | select($cur[$k] != $des[$k]) | "\($scope): update \($k)" ];

  def direct_child_names:
    [ (.projects // {}) | keys[]
      | select(startswith($root + "/"))
      | ltrimstr($root + "/")
      | select(length > 0 and (contains("/") | not)) ];

  . as $doc
  | ($doc | direct_child_names) as $present
  | ([$present[], $exists[]] | unique) as $names
  | [ $names[]
      | . as $n
      | select(
          ($exists | index($n))
          or (($present | index($n)) and (($listed | index($n)) | not))
        )
      | {
          name: $n,
          key: ($root + "/" + $n),
          cur: ($doc.projects[$root + "/" + $n].mcpServers // {}),
          des: ($want.projects[$n] // {})
        }
    ] as $projs
  | ($doc.mcpServers // {}) as $ucur
  | {
      plan: (
        diff("user"; $ucur; $want.user)
        + [ $projs[] | diff(.name; .cur; .des)[] ]
      ),
      doc: (
        (if $ucur != $want.user then .mcpServers = $want.user else . end)
        | reduce $projs[] as $p (.;
            if $p.cur != $p.des then .projects[$p.key].mcpServers = $p.des else . end)
      )
    }
' <<<"$CURRENT")"

PLAN="$(jq -r '.plan[]' <<<"$RESULT")"
[ -n "$PLAN" ] || exit 0

printf '%s\n' "$PLAN"
[ "$DRY_RUN" -eq 0 ] || exit 0

TARGET_DIR="$(dirname "$TARGET")"
mkdir -p "$TARGET_DIR"
TMP="$(mktemp "$TARGET_DIR/.claude.json.XXXXXX")"
TMP_FILES+=("$TMP")
jq --indent 2 '.doc' <<<"$RESULT" >"$TMP"

if [ -f "$TARGET" ]; then
  BACKUP="$TARGET.bak-$(date +%Y%m%d-%H%M%S)"
  cp -p "$TARGET" "$BACKUP"
  chmod --reference="$TARGET" "$TMP"
  echo "backup: $BACKUP"
else
  chmod 600 "$TMP"
fi

mv "$TMP" "$TARGET"
