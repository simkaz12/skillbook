#!/usr/bin/env bash
# Fast-forward a repo to origin's base branch, backing up and reapplying overlapping dirty edits.
set -euo pipefail
set -C

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$HERE/../hooks/scope-map.sh"

repo="."
backup_dir=""
key=""
check=0
no_switch=0

while [ $# -gt 0 ]; do
  case "$1" in
    --repo)       repo="${2:?--repo needs a path}"; shift 2 ;;
    --backup-dir) backup_dir="${2:?--backup-dir needs a path}"; shift 2 ;;
    --key)        key="${2:?--key needs a value}"; shift 2 ;;
    --check)      check=1; shift ;;
    --no-switch)  no_switch=1; shift ;;
    *) echo "usage: pull-base.sh [--repo <path>] [--backup-dir <dir>] [--key <slug>] [--check] [--no-switch]"; exit 2 ;;
  esac
done

refuse() {
  printf 'refused: %s\n' "$1"
  shift
  [ $# -eq 0 ] || printf '  %s\n' "$@"
  echo "nothing in the tree changed"
  exit 3
}

patch_flags=(--binary --no-textconv --no-ext-diff --src-prefix=a/ --dst-prefix=b/)

g() { git -C "$repo" "$@"; }

repo=$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null) || refuse "$repo is not a git repository"
name=$(basename "$(main_checkout "$repo")")
base=$(base_branch "$repo") || refuse "no base branch on file for $name"
branch=$(g symbolic-ref --short -q HEAD || true)

if [ $check -eq 0 ]; then
  for marker in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD BISECT_LOG; do
    if [ -e "$(g rev-parse --path-format=absolute --git-path "$marker")" ]; then
      refuse "a rebase, merge, cherry-pick, revert or bisect is in progress ($marker)"
    fi
  done
  [ -n "$branch" ] || refuse "HEAD is detached"
fi

fetch_ok=1
fetch_out=$(GIT_TERMINAL_PROMPT=0 timeout "${PULL_BASE_FETCH_TIMEOUT:-20}" \
  git -C "$repo" fetch -q origin "$base" 2>&1 </dev/null) || fetch_ok=0
g rev-parse --verify -q "refs/remotes/origin/$base" >/dev/null || fetch_ok=0

if [ $fetch_ok -eq 0 ]; then
  if [ $check -eq 1 ]; then
    printf 'base %s\nbranch %s\nfetch failed\n' "$base" "${branch:-(detached)}"
    exit 0
  fi
  refuse "could not fetch origin $base" "$fetch_out"
fi

overlap=()
mapfile -d '' dirty < <(g diff --name-only --no-renames -z HEAD)
mapfile -d '' upstream < <(g diff --name-only --no-renames -z HEAD "origin/$base")

declare -A moved=()
for f in "${upstream[@]}"; do moved["$f"]=1; done
for f in "${dirty[@]}"; do
  if [ -n "${moved[$f]:-}" ]; then
    overlap+=("$f")
  fi
done

behind=$(g rev-list --count "HEAD..origin/$base")
ahead=$(g rev-list --count "origin/$base..HEAD")

if [ $check -eq 1 ]; then
  printf 'base %s\nbranch %s\nbehind %s\nahead %s\ndirty %s\noverlap %s\n' \
    "$base" "${branch:-(detached)}" "$behind" "$ahead" "${#dirty[@]}" "${#overlap[@]}"
  exit 0
fi

if [ "$branch" = "$base" ]; then
  [ "$ahead" -eq 0 ] || refuse "local $base has $ahead commit(s) that origin/$base lacks" \
    "$(g log --oneline "origin/$base..HEAD" | head -5)"
elif g rev-parse --verify -q "refs/heads/$base" >/dev/null; then
  local_ahead=$(g rev-list --count "origin/$base..refs/heads/$base")
  [ "$local_ahead" -eq 0 ] || refuse "local $base has $local_ahead commit(s) that origin/$base lacks"
fi

if [ "$behind" -eq 0 ]; then
  echo "current: $name $branch is not behind origin/$base ($(g rev-parse --short HEAD))"
  exit 0
fi

old_head=$(g rev-parse --short HEAD)

if [ $no_switch -eq 1 ] && [ "$branch" != "$base" ]; then
  if ! out=$(g fetch -q origin "$base:$base" 2>&1); then
    refuse "could not fast-forward local $base without switching to it" "$out"
  fi
  echo "behind: $name $branch is $behind commit(s) behind origin/$base"
  echo "local $base fast-forwarded to $(g rev-parse --short "refs/heads/$base")"
  echo "no files changed; $branch was not touched"
  exit 0
fi

if [ "$branch" != "$base" ]; then
  other=$(g worktree list --porcelain | awk -v ref="branch refs/heads/$base" -v self="$repo" '
    /^worktree / { path = substr($0, 10) }
    $0 == ref && path != self { print path }')
  [ -z "$other" ] || refuse "$base is checked out in another worktree" "$other"
fi

mapfile -d '' added < <(g diff --name-only --diff-filter=A --no-renames -z HEAD "origin/$base")
clash=()
for f in "${added[@]}"; do
  if [ -e "$repo/$f" ] || [ -L "$repo/$f" ]; then
    clash+=("$f")
  fi
done
[ ${#clash[@]} -eq 0 ] || refuse "untracked or ignored files exist where origin/$base adds files" "${clash[@]}"

for f in "${overlap[@]}"; do
  if ! g cat-file -e "HEAD:$f" 2>/dev/null; then
    refuse "a file added locally is also changed upstream" "$f"
  fi

  if [ -d "$repo/$f" ] && [ ! -L "$repo/$f" ]; then
    refuse "a directory sits where upstream changes a tracked file" "$f"
  fi

  if ! g ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then
    if [ -e "$repo/$f" ] || [ -L "$repo/$f" ]; then
      refuse "a file is out of the index but still on disk, and upstream changes it" "$f"
    fi
  fi
done

: "${key:=$(date +%Y-%m-%d-%H%M%S-%N)}"
: "${backup_dir:=$HOME/.claude/state/pull-base/$name}"
case "$backup_dir" in /*) ;; *) backup_dir="$PWD/$backup_dir" ;; esac
full_patch="$backup_dir/_backup-$name-dirty-before-$key-pull.patch"
overlap_patch="$backup_dir/_overlap-$name-$key.patch"
staged_list="$backup_dir/_staged-$name-$key.txt"
staged_patch="$backup_dir/_staged-$name-$key.patch"

planned=()
[ ${#dirty[@]} -eq 0 ] || planned+=("$full_patch")
[ ${#overlap[@]} -eq 0 ] || planned+=("$overlap_patch" "$staged_list" "$staged_patch")
for f in "${planned[@]}"; do
  if [ -e "$f" ]; then
    refuse "a backup file already exists and is never overwritten; pass a new --key" "$f"
  fi
done

staged_overlap=()
byte_equal=()

if [ ${#dirty[@]} -gt 0 ]; then
  mkdir -p "$backup_dir"
  g diff "${patch_flags[@]}" HEAD > "$full_patch"
  [ -s "$full_patch" ] || refuse "backup patch is missing or empty: $full_patch"
fi

restore_failed() {
  echo "FAILED to put the overlap edits back: $1"
  echo "backup patch: $full_patch"
  echo "overlap patch: $overlap_patch"
  [ ! -s "$staged_patch" ] || echo "staged patch: $staged_patch"
  exit 4
}

restore_overlap() {
  local out
  [ ${#overlap[@]} -gt 0 ] || return 0

  out=$(g apply -p1 "$overlap_patch" 2>&1) || restore_failed "$out"
  if [ -s "$staged_patch" ]; then
    out=$(g apply -p1 --cached "$staged_patch" 2>&1) || restore_failed "$out"
  fi
}

refuse_after_revert() {
  echo "refused: $1"
  echo "$2"
  restore_overlap
  echo "overlap edits put back as they were; backup at $full_patch"
  exit 3
}

if [ ${#overlap[@]} -gt 0 ]; then
  g diff "${patch_flags[@]}" HEAD -- "${overlap[@]}" > "$overlap_patch"
  [ -s "$overlap_patch" ] || refuse "overlap patch is missing or empty: $overlap_patch"

  mapfile -d '' staged < <(g diff --cached --name-only --no-renames -z HEAD -- "${overlap[@]}")
  staged_overlap=("${staged[@]}")
  if [ ${#staged[@]} -gt 0 ]; then
    printf '%s\n' "${staged[@]}" > "$staged_list"
    g diff --cached "${patch_flags[@]}" HEAD -- "${overlap[@]}" > "$staged_patch"
  else
    : > "$staged_list"
  fi

  for f in "${overlap[@]}"; do
    if g diff --quiet --no-textconv --no-ext-diff "origin/$base" -- "$f"; then
      byte_equal+=("$f")
    fi
  done

  if ! out=$(g checkout HEAD -- "${overlap[@]}" 2>&1); then
    refuse_after_revert "could not revert the overlap files" "$out"
  fi
fi

if [ "$branch" != "$base" ]; then
  if ! out=$(g checkout --no-overwrite-ignore "$base" 2>&1); then
    refuse_after_revert "git checkout $base failed" "$out"
  fi
fi

before=$(g rev-parse --short HEAD)
if ! out=$(g merge --no-overwrite-ignore --ff-only -q "origin/$base" 2>&1); then
  if [ "$branch" != "$base" ]; then
    back=$(g checkout "$branch" 2>&1) || restore_failed "could not switch back to $branch: $back"
  fi
  refuse_after_revert "fast-forward to origin/$base failed" "$out"
fi
after=$(g rev-parse --short HEAD)
count=$(g rev-list --count "$before..$after")

conflicted=0
apply_out=""
if [ ${#overlap[@]} -gt 0 ]; then
  if apply_out=$(g apply -p1 --3way "$overlap_patch" 2>&1); then
    g restore --staged -- "${overlap[@]}"
  else
    conflicted=1
  fi
fi

echo "repo: $name"
echo "base: $base"
echo "branch: $branch ($old_head) -> $base"
echo "pulled: $before..$after ($count commits)"

if [ $conflicted -eq 1 ]; then
  unmerged=$(g diff --name-only --diff-filter=U)
  if [ -n "$unmerged" ]; then
    echo "CONFLICT: reapplying the overlap left conflict markers in:"
    echo "$unmerged" | sed 's/^/  /'
  else
    echo "APPLY FAILED: git could not reapply the overlap and wrote no conflict markers."
    echo "The overlap files hold the pulled version; the dirty edits are only in the patches below."
  fi
  echo "git apply said:"
  echo "$apply_out" | sed 's/^/  /'
  echo "tree left as it is; backup at $full_patch"
  echo "overlap patch at $overlap_patch"
  [ ! -s "$staged_patch" ] || echo "staged (index) versions at $staged_patch"
  exit 4
fi

if [ ${#overlap[@]} -gt 0 ]; then
  echo "overlap reverted and reapplied:"
  printf '  %s\n' "${overlap[@]}"
  if [ ${#byte_equal[@]} -gt 0 ]; then
    echo "byte-equal to origin/$base before the pull (reapplied as a no-op):"
    printf '  %s\n' "${byte_equal[@]}"
  fi
  if [ ${#staged_overlap[@]} -gt 0 ]; then
    echo "staged before, unstaged now:"
    printf '  %s\n' "${staged_overlap[@]}"
    echo "their index versions are saved in $staged_patch"
  fi
fi

if [ ${#dirty[@]} -gt 0 ]; then
  echo "backup patch: $full_patch"
  echo "untracked files are not in the patch and were not touched"
fi
exit 0
