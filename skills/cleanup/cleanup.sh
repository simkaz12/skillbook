#!/usr/bin/env bash
set -euo pipefail

PROJECTS="${PROJECTS_ROOT:-$HOME/Projects}"
WORK_REPOS=(crm-api crm-web)
PERSONAL_REPOS=(notes-app)

MODE="dry"
[[ "${1:-}" == "--execute" ]] && MODE="execute"
STAMP="$(date +%Y-%m-%d)"

removed=0
moved=0
skipped=0

dir_empty() { [ -z "$(ls -A "$1" 2>/dev/null)" ]; }

rm_path() {
  local p="$1"
  printf 'RM    %s\n' "$p"
  if [ "$MODE" = execute ]; then
    if ! rm -rf "$p" 2>/dev/null; then
      printf 'SKIP  (no permission, likely root-owned) %s\n' "$p"
      skipped=$((skipped + 1))
      return
    fi
  fi
  removed=$((removed + 1))
}

mv_path() {
  local src="$1" destdir="$2"
  printf 'MV    %s  ->  %s/\n' "$src" "$destdir"
  if [ "$MODE" = execute ]; then
    mkdir -p "$destdir"
    mv "$src" "$destdir"/
  fi
  moved=$((moved + 1))
}

dispose() {
  local src="$1" repo="$2" disposition="$3" kind="$4"
  if [ "$disposition" = trash ]; then
    mv_path "$src" "$repo/.trash/$STAMP/$kind"
  else
    mv_path "$src" "$repo/docs/superpowers/backlog/$kind"
  fi
}

clean_pw_debris() {
  local d="$1/.playwright-mcp" f
  [ -d "$d" ] || return 0
  while IFS= read -r -d '' f; do rm_path "$f"; done < <(
    find "$d" -maxdepth 1 -type f \
      \( -name '*.png' -o -name '*.log' -o -name '*.yml' -o -name '*.webm' -o -name '*.zip' \) \
      ! -name 'auth.json' -print0
  )
}

process_plans() {
  local repo="$1" disposition="$2"
  local base="$repo/docs/superpowers" plansdir
  plansdir="$base/plans"
  [ -d "$plansdir" ] || return 0
  local plan name spec
  for plan in "$plansdir"/*/; do
    [ -d "$plan" ] || continue
    plan="${plan%/}"
    name="$(basename "$plan")"
    if [ -d "$plan/tasks" ] && dir_empty "$plan/tasks" && [ -d "$plan/done" ] && ! dir_empty "$plan/done"; then
      dispose "$plan" "$repo" "$disposition" "plans"
      spec="$base/specs/$name.md"
      [ -f "$spec" ] && dispose "$spec" "$repo" "$disposition" "specs"
    fi
  done
}

process_qa() {
  local repo="$1" disposition="$2"
  local qadir="$repo/docs/qa" q
  [ -d "$qadir" ] || return 0
  for q in "$qadir"/*/; do
    [ -d "$q" ] || continue
    q="${q%/}"
    if { [ ! -d "$q/failed" ] || dir_empty "$q/failed"; } &&
      { [ ! -d "$q/incomplete" ] || dir_empty "$q/incomplete"; } &&
      ! dir_empty "$q"; then
      dispose "$q" "$repo" "$disposition" "qa"
    fi
  done
}

process_gauntlet() {
  local repo="$1" disposition="$2"
  local gauntletdir="$repo/docs/gauntlet" specsdir="$repo/docs/specs"
  [ -d "$gauntletdir" ] || return 0
  local run name spec
  for run in "$gauntletdir"/*/; do
    [ -d "$run" ] || continue
    run="${run%/}"
    name="$(basename "$run")"
    if [ -f "$run/report.md" ]; then
      dispose "$run" "$repo" "$disposition" "gauntlet"
      spec="$specsdir/$name.md"
      [ -f "$spec" ] && dispose "$spec" "$repo" "$disposition" "specs"
    fi
  done
}

printf '== playwright debris (all repos, auth.json preserved) ==\n'
for r in "${WORK_REPOS[@]}" "${PERSONAL_REPOS[@]}"; do clean_pw_debris "$PROJECTS/$r"; done

printf '\n== work repos: finished plans/specs/qa/gauntlet -> .trash ==\n'
for r in "${WORK_REPOS[@]}"; do
  process_plans "$PROJECTS/$r" trash
  process_qa "$PROJECTS/$r" trash
  process_gauntlet "$PROJECTS/$r" trash
done

printf '\n== personal repos: finished plans/specs/qa/gauntlet -> docs/superpowers/backlog ==\n'
for r in "${PERSONAL_REPOS[@]}"; do
  process_plans "$PROJECTS/$r" backlog
  process_qa "$PROJECTS/$r" backlog
  process_gauntlet "$PROJECTS/$r" backlog
done

printf '\n== %s removed, %s moved, %s skipped (mode=%s) ==\n' "$removed" "$moved" "$skipped" "$MODE"
[ "$MODE" = dry ] && printf 'dry-run only — nothing changed. re-run with --execute to apply.\n'
exit 0
