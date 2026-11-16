#!/usr/bin/env bash
set -uo pipefail

root=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "FATAL: not a git repo"; exit 1; }
cd "$root" || exit 1
gitdir=$(git rev-parse --git-dir)

branch=$(git rev-parse --abbrev-ref HEAD)
[ "$branch" = "HEAD" ] && branch="DETACHED @ $(git rev-parse --short HEAD)"

remote=$(git remote get-url origin 2>/dev/null || echo none)
case "$remote" in
  *github.com*)    host=github ;;
  *bitbucket.org*) host=bitbucket ;;
  none)            host=none ;;
  *)               host=other ;;
esac

default=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')
if [ -z "$default" ]; then
  for c in main master; do
    if git show-ref --verify --quiet "refs/heads/$c"; then default=$c; break; fi
  done
fi
[ -z "$default" ] && default=unknown

upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || echo none)
ahead=0; behind=0
if [ "$upstream" != none ]; then
  counts=$(git rev-list --left-right --count "$upstream...HEAD" 2>/dev/null || printf '0\t0')
  behind=$(printf '%s' "$counts" | cut -f1)
  ahead=$(printf '%s' "$counts" | cut -f2)
fi

op=none
if [ -d "$gitdir/rebase-merge" ] || [ -d "$gitdir/rebase-apply" ]; then op=REBASE; fi
if [ -f "$gitdir/MERGE_HEAD" ]; then op=MERGE; fi
if [ -f "$gitdir/CHERRY_PICK_HEAD" ]; then op=CHERRY-PICK; fi
if [ -f "$gitdir/BISECT_LOG" ]; then op=BISECT; fi

worktree=no
git rev-parse --is-inside-work-tree >/dev/null 2>&1 && [ -f "$gitdir" ] && worktree=yes

printf 'repo      %s  (%s)\n' "$(basename "$root")" "$root"
printf 'branch    %s\n' "$branch"
printf 'default   %s\n' "$default"
printf 'host      %s  (%s)\n' "$host" "$remote"
printf 'upstream  %s   ahead %s  behind %s\n' "$upstream" "$ahead" "$behind"
printf 'inprog    %s\n' "$op"
printf 'worktree  %s\n' "$worktree"

echo
echo "--- tracked changes"
git --no-pager diff --stat HEAD 2>/dev/null | tail -40 || true
[ -z "$(git --no-pager diff --stat HEAD 2>/dev/null)" ] && echo "(none)"

echo
echo "--- staged"
git --no-pager diff --cached --stat 2>/dev/null || true
[ -z "$(git --no-pager diff --cached --stat 2>/dev/null)" ] && echo "(none)"

echo
echo "--- untracked"
untracked=$(git ls-files --others --exclude-standard)
[ -n "$untracked" ] && printf '%s\n' "$untracked" | head -40 || echo "(none)"

echo
echo "--- risky paths in the change set"
risky=$( { git --no-pager diff --name-only HEAD; git ls-files --others --exclude-standard; } 2>/dev/null \
  | grep -Ei '(^|/)\.env|\.pem$|\.p12$|\.key$|id_rsa|credentials|secrets?\.(ya?ml|json)|\.(zip|tar|gz|mp4|sqlite|db)$' || true )
[ -n "$risky" ] && printf '%s\n' "$risky" || echo "(none)"

echo
echo "--- recent subjects (style reference)"
git --no-pager log --no-merges --pretty=format:'%s' -8 2>/dev/null || true
echo

echo
echo "--- open PR"
if [ "$host" = github ] && command -v gh >/dev/null 2>&1; then
  gh pr view --json number,url,state,title 2>/dev/null || echo "(none for this branch)"
else
  echo "(host is $host — check manually)"
fi
