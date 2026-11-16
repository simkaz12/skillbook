#!/usr/bin/env bash
set -euo pipefail

SKILLBOOK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CLAUDE_HOME="$HOME/.claude"

DRY_RUN=0
NO_DOCTOR=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --no-doctor) NO_DOCTOR=1 ;;
    *) echo "usage: install.sh [--dry-run] [--no-doctor]" >&2; exit 1 ;;
  esac
done

STAMP="$(date +%Y%m%d-%H%M%S)"

say() {
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "would: $1"
  else
    echo "did: $1"
  fi
}

warn() {
  echo "warn: $1"
}

unique_path() {
  local desired="$1"
  local p="$desired"
  local i=2
  while [ -e "$p" ]; do
    p="$desired-$i"
    i=$((i+1))
  done
  printf '%s' "$p"
}

ensure_dir() {
  local dir="$1"
  [ -d "$dir" ] && return 0

  say "mkdir -p $dir"
  [ "$DRY_RUN" -eq 1 ] || mkdir -p "$dir"
}

link_entry() {
  local dest_rel="$1" src_rel="$2"
  local dest="$CLAUDE_HOME/$dest_rel"
  local target="$SKILLBOOK/$src_rel"

  if [ -L "$dest" ]; then
    local current
    current=$(readlink "$dest")
    [ "$current" = "$target" ] && return 0

    say "relink $dest -> $target (was $current)"
    [ "$DRY_RUN" -eq 1 ] || ln -sfnT "$target" "$dest"
    return 0
  fi

  if [ -e "$dest" ]; then
    local backup
    backup=$(unique_path "$dest.bak-$STAMP")
    say "move $dest to $backup (real file/dir at farm entry)"
    [ "$DRY_RUN" -eq 1 ] || mv "$dest" "$backup"
  fi

  say "link $dest -> $target"
  [ "$DRY_RUN" -eq 1 ] || ln -sfnT "$target" "$dest"
}

ensure_dir "$CLAUDE_HOME"
ensure_dir "$CLAUDE_HOME/corpus-tools"

FARM_ENTRIES=(
  "agents:agents"
  "commands:commands"
  "hooks:hooks"
  "output-styles:output-styles"
  "skills:skills"
  "themes:themes"
  "settings.json:settings.json"
  "statusline-command.sh:statusline-command.sh"
  "CONTEXT-LOAD.md:CONTEXT-LOAD.md"
  "LANGUAGE.md:LANGUAGE.md"
  "NOTEBOOK.md:NOTEBOOK.md"
  "CLAUDE.md:GLOBAL-CLAUDE.md"
  "GLOBAL-CORE.md:GLOBAL-CORE.md"
  "corpus-tools/corpus_capture:corpus-tools/corpus_capture"
)

for entry in "${FARM_ENTRIES[@]}"; do
  link_entry "${entry%%:*}" "${entry#*:}"
done

CURRENT_HOOKS_PATH="$(git -C "$SKILLBOOK" config --get core.hooksPath || true)"
if [ "$CURRENT_HOOKS_PATH" != ".githooks" ]; then
  say "git -C $SKILLBOOK config core.hooksPath .githooks"
  [ "$DRY_RUN" -eq 1 ] || git -C "$SKILLBOOK" config core.hooksPath .githooks
fi

BASHFILTER="$HOME/.local/share/bashfilter/bin/bashfilter-chain"
[ -x "$BASHFILTER" ] || warn "bashfilter missing at $BASHFILTER"
command -v python3 >/dev/null 2>&1 || warn "python3 missing"
command -v jq >/dev/null 2>&1 || warn "jq missing"

if command -v jq >/dev/null 2>&1 && [ -f "$SKILLBOOK/.mcp.json" ]; then
  TABULARIUM_URL="$(jq -r '.mcpServers["tabularium-mcp"].url // empty' "$SKILLBOOK/.mcp.json")"
  if [ -n "$TABULARIUM_URL" ]; then
    code="$(curl -s -m 3 -o /dev/null -w '%{http_code}' "$TABULARIUM_URL" || true)"
    [ "${code:-000}" != "000" ] || warn "Tabularium unreachable at $TABULARIUM_URL"
  fi
fi

CODEX_HOME_DIR="$HOME/.codex"
if [ -d "$CODEX_HOME_DIR" ]; then
  ensure_dir "$CODEX_HOME_DIR/skills"
  ensure_dir "$CODEX_HOME_DIR/agents"

  if [ "$DRY_RUN" -eq 1 ]; then
    if [ -d "$CODEX_HOME_DIR/skills" ] && [ -d "$CODEX_HOME_DIR/agents" ]; then
      bash "$SKILLBOOK/scripts/sync-codex.sh" --dry-run
    else
      say "run scripts/sync-codex.sh --dry-run (after $CODEX_HOME_DIR/skills and $CODEX_HOME_DIR/agents exist)"
    fi
  else
    bash "$SKILLBOOK/scripts/sync-codex.sh"
  fi
fi

if command -v jq >/dev/null 2>&1; then
  if [ "$DRY_RUN" -eq 1 ]; then
    bash "$SKILLBOOK/scripts/sync-mcp.sh" --dry-run
  else
    bash "$SKILLBOOK/scripts/sync-mcp.sh" || warn "sync-mcp.sh failed, MCP servers not synced"
  fi
fi

if [ "$NO_DOCTOR" -eq 0 ] && [ "$DRY_RUN" -eq 0 ]; then
  bash "$SKILLBOOK/scripts/doctor.sh"
fi
