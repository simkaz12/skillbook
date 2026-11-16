#!/usr/bin/env bash
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

export PROJECTS_ROOT="$TMP/root"
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t

mkdir -p "$PROJECTS_ROOT/skillbook/sub" "$PROJECTS_ROOT/unmapped" "$TMP/outside" "$TMP/wt"

make_repo() {
  git init -q "$1"
  git -C "$1" commit -q --allow-empty -m init
}

make_repo "$PROJECTS_ROOT/skillbook"
make_repo "$PROJECTS_ROOT/unmapped"
git -C "$PROJECTS_ROOT/skillbook" worktree add -q "$TMP/wt/skillbook-wt" -b feat
git -C "$PROJECTS_ROOT/unmapped" worktree add -q "$TMP/wt/unmapped-wt" -b feat

source "$HERE/scope-map.sh"

fail=0
expect() {
  local label="$1" want="$2" got rc
  shift 2
  got=$("$@" 2>/dev/null); rc=$?
  if [ "$want" = "FAIL" ]; then
    [ "$rc" -ne 0 ] && [ -z "$got" ] && return 0
  else
    [ "$rc" -eq 0 ] && [ "$got" = "$want" ] && return 0
  fi
  echo "not ok: $label (rc=$rc got='$got')"
  fail=1
}

expect "repo root" skillbook path_scope "$PROJECTS_ROOT/skillbook"
expect "worktree" skillbook path_scope "$TMP/wt/skillbook-wt"
expect "subdir" skillbook path_scope "$PROJECTS_ROOT/skillbook/sub"
expect "non-git outside root" FAIL path_scope "$TMP/outside"
expect "unmapped worktree" FAIL path_scope "$TMP/wt/unmapped-wt"

unset PULL_BASE_BRANCH
mkdir -p "$PROJECTS_ROOT/crm-api" "$PROJECTS_ROOT/tabularium"
make_repo "$PROJECTS_ROOT/crm-api"
make_repo "$PROJECTS_ROOT/tabularium"
expect "base dev" dev base_branch "$PROJECTS_ROOT/crm-api"
expect "base master" master base_branch "$PROJECTS_ROOT/skillbook"
expect "base main" main base_branch "$PROJECTS_ROOT/tabularium"
expect "base subdir" master base_branch "$PROJECTS_ROOT/skillbook/sub"
expect "base worktree" master base_branch "$TMP/wt/skillbook-wt"
expect "base unknown repo" FAIL base_branch "$PROJECTS_ROOT/unmapped"
expect "base non-git" FAIL base_branch "$TMP/outside"
PULL_BASE_BRANCH=trunk expect "base env override" trunk base_branch "$PROJECTS_ROOT/unmapped"

[ "$fail" -eq 0 ] && echo ok
exit "$fail"
