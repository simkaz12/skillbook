#!/usr/bin/env bash
set -euo pipefail

SKILLBOOK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
source "$SKILLBOOK/scripts/codex-agent-config.sh"

DRY_RUN=0
RULES_ONLY=0
AGENTS_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --dry-run)
      [ "$DRY_RUN" -eq 0 ] || { echo "usage: sync-codex.sh [--dry-run] [--rules-only | --agents-only]" >&2; exit 1; }
      DRY_RUN=1
      ;;
    --rules-only)
      [ "$RULES_ONLY" -eq 0 ] && [ "$AGENTS_ONLY" -eq 0 ] || { echo "usage: sync-codex.sh [--dry-run] [--rules-only | --agents-only]" >&2; exit 1; }
      RULES_ONLY=1
      ;;
    --agents-only)
      [ "$AGENTS_ONLY" -eq 0 ] && [ "$RULES_ONLY" -eq 0 ] || { echo "usage: sync-codex.sh [--dry-run] [--rules-only | --agents-only]" >&2; exit 1; }
      AGENTS_ONLY=1
      ;;
    *)
      echo "usage: sync-codex.sh [--dry-run] [--rules-only | --agents-only]" >&2
      exit 1
      ;;
  esac
done

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

if [ "$RULES_ONLY" -eq 0 ] && [ "$AGENTS_ONLY" -eq 0 ]; then
  SKILLS_DIR="$CODEX_HOME/skills"
  [ -d "$SKILLS_DIR" ] || { echo "SKILLS_DIR $SKILLS_DIR missing" >&2; exit 1; }

  PRUNE_DIR="$CODEX_HOME/skills.pruned-$(date +%Y%m%d)"

while IFS= read -r -d '' entry; do
  base=$(basename "$entry")
  if [ -L "$entry" ]; then
    target=$(readlink "$entry")
    case "$target" in
      "$SKILLBOOK/skills/"*)
        if [ ! -f "$SKILLBOOK/skills/$base/SKILL.md" ]; then
          dest=$(unique_path "$PRUNE_DIR/$base")
          if [ "$DRY_RUN" -eq 1 ]; then
            echo "would: mv $entry to $dest (stale skillbook link)"
          else
            mkdir -p "$PRUNE_DIR"
            mv "$entry" "$dest"
            echo "did: mv $entry to $dest (stale skillbook link)"
          fi
        fi
        ;;
      *)
        if [ -f "$SKILLBOOK/skills/$base/SKILL.md" ]; then
          if [ "$DRY_RUN" -eq 1 ]; then
            echo "would: rm $entry (collides with skillbook skill $base)"
          else
            rm "$entry"
            echo "did: rm $entry (collides with skillbook skill $base)"
          fi
        fi
        ;;
    esac
  elif [ -d "$entry" ]; then
    dest=$(unique_path "$PRUNE_DIR/$base")
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "would: mv $entry to $dest"
    else
      mkdir -p "$PRUNE_DIR"
      mv "$entry" "$dest"
      echo "did: mv $entry to $dest"
    fi
  fi
done < <(find "$SKILLS_DIR" -mindepth 1 -maxdepth 1 ! -name .system -print0)

while IFS= read -r -d '' d; do
  [ -f "$d/SKILL.md" ] || continue
  name=$(basename "$d")
  link="$SKILLS_DIR/$name"
  desired="$d/"
  if [ -e "$link" ] && [ ! -L "$link" ]; then
    pruned=$(unique_path "$PRUNE_DIR/$name.$(date +%H%M%S)")
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "would: mv $link to $pruned (regular file at skill name $name)"
    else
      mkdir -p "$PRUNE_DIR"
      mv "$link" "$pruned"
      echo "did: mv $link to $pruned (regular file at skill name $name)"
    fi
  fi
  current=""
  if [ -L "$link" ]; then
    current=$(readlink "$link")
  fi
  if [ "$current" != "$desired" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "would: symlink $link -> $desired"
    else
      ln -sfnT "$desired" "$link"
      echo "did: symlink $link -> $desired"
    fi
  fi
done < <(find "$SKILLBOOK/skills" -mindepth 1 -maxdepth 1 -type d -print0)

if [ "$DRY_RUN" -eq 0 ]; then
  missing=()
  while IFS= read -r -d '' d; do
    [ -f "$d/SKILL.md" ] || continue
    name=$(basename "$d")
    link="$SKILLS_DIR/$name"
    if [ -L "$link" ]; then
      target=$(readlink "$link")
      case "$target" in
        "$SKILLBOOK/skills/"*) continue ;;
      esac
    fi
    missing+=("$link")
  done < <(find "$SKILLBOOK/skills" -mindepth 1 -maxdepth 1 -type d -print0)
  if [ "${#missing[@]}" -gt 0 ]; then
    for m in "${missing[@]}"; do
      echo "missing: $m" >&2
    done
    exit 1
  fi
fi
fi

process_agent() {
  local name="$1"
  local file="$SKILLBOOK/agents/$name.md"

  local first_line
  first_line=$(sed -n '1p' "$file")
  [ "$first_line" = "---" ] || { echo "agents/$name.md does not start with ---" >&2; exit 1; }

  local second_dash
  second_dash=$(awk 'NR>1 && $0=="---" {print NR; exit}' "$file")
  [ -n "$second_dash" ] || { echo "agents/$name.md has no closing ---" >&2; exit 1; }

  local fm
  fm=$(sed -n "2,$((second_dash-1))p" "$file")

  local desc_count
  desc_count=$(printf '%s\n' "$fm" | grep -c '^description:' || true)
  [ "$desc_count" -eq 1 ] || { echo "agents/$name.md: expected exactly one description: line, found $desc_count" >&2; exit 1; }

  local desc_line_num
  desc_line_num=$(printf '%s\n' "$fm" | grep -n '^description:' | cut -d: -f1)
  local fm_line_count
  fm_line_count=$(printf '%s\n' "$fm" | wc -l)
  if [ "$desc_line_num" -lt "$fm_line_count" ]; then
    local next_line
    next_line=$(printf '%s\n' "$fm" | sed -n "$((desc_line_num+1))p")
    if ! [[ "$next_line" =~ ^[A-Za-z_]+: ]]; then
      echo "agents/$name.md: description: value spans multiple lines" >&2
      exit 1
    fi
  fi

  local description
  description=$(printf '%s\n' "$fm" | sed -n '/^description:/s/^description:[[:space:]]*//p')

  local model_raw codex_model codex_model_reasoning_effort
  model_raw=$(printf '%s\n' "$fm" | sed -n '/^model:/s/^model:[[:space:]]*//p')
  local model
  model=$(codex_model_for_claude_model "$model_raw") || {
    echo "agents/$name.md: unexpected model value '$model_raw'" >&2
    exit 1
  }
  local codex_model_count
  codex_model_count=$(printf '%s\n' "$fm" | grep -c '^codex_model:' || true)
  [ "$codex_model_count" -le 1 ] || { echo "agents/$name.md: expected at most one codex_model: line, found $codex_model_count" >&2; exit 1; }
  codex_model=$(printf '%s\n' "$fm" | sed -n '/^codex_model:/s/^codex_model:[[:space:]]*//p')
  if [ -n "$codex_model" ]; then
    codex_model_supported "$codex_model" || {
      echo "agents/$name.md: unsupported codex_model value '$codex_model'" >&2
      exit 1
    }
    model="$codex_model"
  fi
  model=$(codex_resolve_model "$model") || exit 1
  local reasoning_count
  reasoning_count=$(printf '%s\n' "$fm" | grep -c '^codex_model_reasoning_effort:' || true)
  [ "$reasoning_count" -le 1 ] || { echo "agents/$name.md: expected at most one codex_model_reasoning_effort: line, found $reasoning_count" >&2; exit 1; }
  codex_model_reasoning_effort=$(printf '%s\n' "$fm" | sed -n '/^codex_model_reasoning_effort:/s/^codex_model_reasoning_effort:[[:space:]]*//p')
  if [ -n "$codex_model_reasoning_effort" ]; then
    codex_effort_supported "$codex_model_reasoning_effort" || {
      echo "agents/$name.md: unsupported codex_model_reasoning_effort value '$codex_model_reasoning_effort'" >&2
      exit 1
    }
  fi

  local cap_count
  cap_count=$(printf '%s\n' "$fm" | grep -c '^capability:' || true)
  [ "$cap_count" -eq 1 ] || { echo "agents/$name.md: expected exactly one capability: line, found $cap_count" >&2; exit 1; }

  local capability
  capability=$(printf '%s\n' "$fm" | sed -n '/^capability:/s/^capability:[[:space:]]*//p')

  local sandbox_mode
  case "$capability" in
    read-only) sandbox_mode=read-only ;;
    write) sandbox_mode=workspace-write ;;
    *) echo "agents/$name.md: unexpected capability value '$capability'" >&2; exit 1 ;;
  esac

  local body
  body=$(tail -n "+$((second_dash+1))" "$file")
  case "$body" in
    *"'''"*) echo "agents/$name.md: body contains ''' which breaks the TOML literal string" >&2; exit 1 ;;
  esac

  local esc_description
  esc_description=$(printf '%s' "$description" | sed 's/\\/\\\\/g; s/"/\\"/g')

  local tmp
  tmp=$(mktemp "$CODEX_HOME/agents/.$name.toml.XXXXXX")
  TMP_FILES+=("$tmp")
  {
    printf '# generated by skillbook/scripts/sync-codex.sh from agents/%s.md — do not edit\n' "$name"
    printf 'name = "%s"\n' "$name"
    printf 'description = "%s"\n' "$esc_description"
    printf 'model = "%s"\n' "$model"
    if [ -n "$codex_model_reasoning_effort" ]; then
      printf 'model_reasoning_effort = "%s"\n' "$codex_model_reasoning_effort"
    fi
    printf 'sandbox_mode = "%s"\n' "$sandbox_mode"
    printf "developer_instructions = '''\n"
    printf '%s\n' "$body"
    printf "'''\n"
  } > "$tmp"

  local target="$CODEX_HOME/agents/$name.toml"
  if [ -f "$target" ] && cmp -s "$tmp" "$target"; then
    rm -f "$tmp"
    return
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "would: write $target"
    rm -f "$tmp"
  else
    mv "$tmp" "$target"
    echo "did: write $target"
  fi
}

if [ "$RULES_ONLY" -eq 0 ]; then
  for n in bolt hand-do hand-ex spec-runner spec-reviewer; do
    process_agent "$n"
  done
fi

MARKER='<!-- generated by skillbook/scripts/sync-codex.sh from GLOBAL-CORE.md + CODEX-TAIL.md — edit those, then re-run -->'
AGENTS_TARGET="$CODEX_HOME/AGENTS.md"

if [ -f "$AGENTS_TARGET" ]; then
  first_line=$(sed -n '1p' "$AGENTS_TARGET")
  if [ "$first_line" != "$MARKER" ]; then
    BACKUP=$(unique_path "$CODEX_HOME/AGENTS.md.bak-$(date +%Y%m%d-%H%M%S)")
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "would: cp $AGENTS_TARGET $BACKUP"
    else
      cp "$AGENTS_TARGET" "$BACKUP"
      echo "did: cp $AGENTS_TARGET $BACKUP"
    fi
  fi
fi

if [ "$DRY_RUN" -eq 1 ]; then
  AGENTS_TMP=$(mktemp "${TMPDIR:-/tmp}/sync-codex-AGENTS.md.XXXXXX")
else
  AGENTS_TMP=$(mktemp "$CODEX_HOME/.AGENTS.md.XXXXXX")
fi
TMP_FILES+=("$AGENTS_TMP")
{
  printf '%s\n' "$MARKER"
  printf '\n'
  cat "$SKILLBOOK/GLOBAL-CORE.md"
  printf '\n'
  cat "$SKILLBOOK/CODEX-TAIL.md"
} > "$AGENTS_TMP"

if [ -f "$AGENTS_TARGET" ] && cmp -s "$AGENTS_TMP" "$AGENTS_TARGET"; then
  rm -f "$AGENTS_TMP"
else
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "would: write $AGENTS_TARGET"
    rm -f "$AGENTS_TMP"
  else
    mv "$AGENTS_TMP" "$AGENTS_TARGET"
    echo "did: write $AGENTS_TARGET"
  fi
fi

if [ "$RULES_ONLY" -eq 0 ] && [ "$AGENTS_ONLY" -eq 0 ]; then
  HOOKS_TARGET="$CODEX_HOME/hooks.json"
  HOOKS_DESIRED="$SKILLBOOK/codex/hooks.json"

if [ -e "$HOOKS_TARGET" ] && [ ! -L "$HOOKS_TARGET" ]; then
  HOOKS_BACKUP=$(unique_path "$CODEX_HOME/hooks.json.bak-$(date +%Y%m%d-%H%M%S)")
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "would: mv $HOOKS_TARGET $HOOKS_BACKUP"
  else
    mv "$HOOKS_TARGET" "$HOOKS_BACKUP"
    echo "did: mv $HOOKS_TARGET $HOOKS_BACKUP"
  fi
fi

HOOKS_CURRENT=""
if [ -L "$HOOKS_TARGET" ]; then
  HOOKS_CURRENT=$(readlink "$HOOKS_TARGET")
fi
if [ "$HOOKS_CURRENT" != "$HOOKS_DESIRED" ]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "would: symlink $HOOKS_TARGET -> $HOOKS_DESIRED"
  else
    ln -sfnT "$HOOKS_DESIRED" "$HOOKS_TARGET"
    echo "did: symlink $HOOKS_TARGET -> $HOOKS_DESIRED"
  fi
fi
fi
