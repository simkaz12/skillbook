#!/usr/bin/env bash
# Tests scripts/pull-base.sh against throwaway origin and clone repos.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PULL="$HERE/../pull-base.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
export PULL_BASE_BRANCH=main

fail=0
ok() { echo "ok: $1"; }
bad() { echo "not ok: $1"; fail=1; }
check() {
  local label="$1"
  shift
  if "$@"; then ok "$label"; else bad "$label"; fi
}

OUT=""
RC=0
run_pull() {
  OUT=$(bash "$PULL" --repo "$B" --backup-dir "$BK" --key k "$@" 2>&1)
  RC=$?
}

out_has() { grep -qF -- "$1" <<<"$OUT"; }

scenario() {
  local n="$1"
  W="$TMP/$n"
  O="$W/origin.git"
  A="$W/clone-a"
  B="$W/clone-b"
  BK="$W/backup"
  mkdir -p "$W"
  git init -q --bare -b main "$O"
  git clone -q "$O" "$A" 2>/dev/null
  git -C "$A" checkout -q -b main
  seq 1 10 > "$A/a.txt"
  echo one > "$A/b.txt"
  echo two > "$A/c.txt"
  git -C "$A" add -A
  git -C "$A" commit -q -m init
  git -C "$A" push -q origin main 2>/dev/null
  git clone -q "$O" "$B" 2>/dev/null
}

a_commit() {
  git -C "$A" add -A
  git -C "$A" commit -q -m "$1"
  git -C "$A" push -q origin main 2>/dev/null
}

origin_head() { git -C "$O" rev-parse main; }
b_head() { git -C "$B" rev-parse HEAD; }

scenario 1
run_pull
check "1 up to date: exit 0" test "$RC" -eq 0
check "1 up to date: prints current" out_has "current"

scenario 2
echo more >> "$A/b.txt"
a_commit "more b"
run_pull
check "2 behind clean: exit 0" test "$RC" -eq 0
check "2 behind clean: HEAD == origin" test "$(b_head)" = "$(origin_head)"

scenario 3
sed -i '1s/.*/first/' "$A/a.txt"
a_commit "edit line 1"
sed -i '10s/.*/last/' "$B/a.txt"
git -C "$B" add a.txt
run_pull
check "3 dirty overlap: exit 0" test "$RC" -eq 0
check "3 dirty overlap: HEAD == origin" test "$(b_head)" = "$(origin_head)"
check "3 dirty overlap: pulled change present" test "$(sed -n 1p "$B/a.txt")" = first
check "3 dirty overlap: dirty edit present" test "$(sed -n 10p "$B/a.txt")" = last
check "3 dirty overlap: file unstaged" git -C "$B" diff --cached --quiet
check "3 dirty overlap: file still modified" test -n "$(git -C "$B" diff --name-only)"
check "3 dirty overlap: backup patch has the edit" grep -q '^+last' "$BK/_backup-clone-b-dirty-before-k-pull.patch"
check "3 dirty overlap: staged list names the file" grep -qx a.txt "$BK/_staged-clone-b-k.txt"
check "3 dirty overlap: report names unstaged path" out_has "staged before, unstaged now"

scenario 4
sed -i '1s/.*/first/' "$A/a.txt"
a_commit "edit line 1"
sed -i '1s/.*/first/' "$B/a.txt"
run_pull
check "4 byte-equal: exit 0" test "$RC" -eq 0
check "4 byte-equal: report names it" bash -c "grep -A1 'byte-equal' <<<\"\$1\" | grep -q a.txt" _ "$OUT"
check "4 byte-equal: tree clean afterwards" test -z "$(git -C "$B" status --porcelain)"

scenario 5
echo more >> "$A/b.txt"
a_commit "more b"
echo local > "$B/b.txt"
git -C "$B" commit -q -am "local only"
echo dirty >> "$B/c.txt"
before=$(b_head)
status_before=$(git -C "$B" status --porcelain)
run_pull
check "5 local-only commit: exit 3" test "$RC" -eq 3
check "5 local-only commit: HEAD unchanged" test "$(b_head)" = "$before"
check "5 local-only commit: tree untouched" test "$(git -C "$B" status --porcelain)" = "$status_before"
check "5 local-only commit: dirty edit kept" grep -qx dirty "$B/c.txt"

scenario 6
sed -i '1s/.*/first/' "$A/a.txt"
a_commit "edit line 1"
git -C "$B" checkout -q -b feat
echo edit >> "$B/c.txt"
run_pull
check "6 feature branch: exit 0" test "$RC" -eq 0
check "6 feature branch: now on main" test "$(git -C "$B" branch --show-current)" = main
check "6 feature branch: HEAD == origin" test "$(b_head)" = "$(origin_head)"
check "6 feature branch: dirty file still dirty" test "$(git -C "$B" diff --name-only)" = c.txt

scenario 7
sed -i '5s/.*/theirs/' "$A/a.txt"
a_commit "edit line 5"
sed -i '5s/.*/mine/' "$B/a.txt"
run_pull
check "7 conflict: exit 4" test "$RC" -eq 4
check "7 conflict: markers present" grep -q '^<<<<<<<' "$B/a.txt"
check "7 conflict: backup path printed" out_has "$BK/_backup-clone-b-dirty-before-k-pull.patch"
check "7 conflict: backup file exists" test -s "$BK/_backup-clone-b-dirty-before-k-pull.patch"
check "7 conflict: HEAD == origin" test "$(b_head)" = "$(origin_head)"

scenario 8
sed -i '1s/.*/first/' "$A/a.txt"
a_commit "edit line 1"
echo edit >> "$B/c.txt"
before=$(b_head)
run_pull --check
check "8 check: exit 0" test "$RC" -eq 0
check "8 check: prints behind count" out_has "behind 1"
check "8 check: prints dirty count" out_has "dirty 1"
check "8 check: HEAD unchanged" test "$(b_head)" = "$before"
check "8 check: working copy unchanged" test "$(git -C "$B" diff --name-only)" = c.txt

scenario 9
echo new > "$A/new.txt"
a_commit "add new.txt"
echo mine > "$B/new.txt"
before=$(b_head)
run_pull
check "9 untracked clash: exit 3" test "$RC" -eq 3
check "9 untracked clash: lists the file" out_has "new.txt"
check "9 untracked clash: HEAD unchanged" test "$(b_head)" = "$before"
check "9 untracked clash: file untouched" grep -qx mine "$B/new.txt"

scenario 10
sed -i '1s/.*/first/' "$A/a.txt"
a_commit "edit line 1"
git -C "$B" checkout -q -b feat
echo edit >> "$B/c.txt"
run_pull --no-switch
check "10 no-switch: exit 0" test "$RC" -eq 0
check "10 no-switch: still on feat" test "$(git -C "$B" branch --show-current)" = feat
check "10 no-switch: local main fast-forwarded" test "$(git -C "$B" rev-parse main)" = "$(origin_head)"
check "10 no-switch: dirty file untouched" test "$(git -C "$B" diff --name-only)" = c.txt

scenario 11
git -C "$B" remote set-url origin "$W/missing.git"
run_pull --check
check "11 fetch failure in check: exit 0" test "$RC" -eq 0
check "11 fetch failure in check: says so" out_has "fetch failed"
run_pull
check "11 fetch failure: exit 3" test "$RC" -eq 3

scenario 12
unset PULL_BASE_BRANCH
run_pull
check "12 no base on file: exit 3" test "$RC" -eq 3
check "12 no base on file: says so" out_has "no base branch on file"
export PULL_BASE_BRANCH=main

scenario 13
sed -i '1s/.*/first/' "$A/a.txt"
a_commit "edit line 1"
sed -i '10s/.*/last/' "$B/a.txt"
OUT=$(cd "$W" && bash "$PULL" --repo clone-b --backup-dir rel/backup --key k 2>&1)
RC=$?
check "13 relative backup dir: exit 0" test "$RC" -eq 0
check "13 relative backup dir: dirty edit reapplied" test "$(sed -n 10p "$B/a.txt")" = last
check "13 relative backup dir: pulled change present" test "$(sed -n 1p "$B/a.txt")" = first
check "13 relative backup dir: patch under the caller's cwd" test -s "$W/rel/backup/_backup-clone-b-dirty-before-k-pull.patch"

scenario 14
HOOK="$HERE/../../hooks/base-branch-check.sh"
hook_msg() { printf '{"cwd":"%s"}' "$B" | bash "$HOOK" | jq -r .hookSpecificOutput.additionalContext; }
OUT=$(hook_msg)
check "14 hook current: says current" out_has "Base branch main: current."
sed -i '1s/.*/first/' "$A/a.txt"
a_commit "edit line 1"
echo edit >> "$B/c.txt"
OUT=$(hook_msg)
check "14 hook behind: reports count" out_has "behind origin by 1 commits (0 dirty files overlap)"
check "14 hook behind: suggests --no-switch" out_has "pull-base.sh --no-switch before starting work"
git -C "$B" remote set-url origin "$W/missing.git"
OUT=$(hook_msg)
check "14 hook fetch failure: says so" out_has "could not fetch origin"

scenario 15
echo more >> "$A/b.txt"
a_commit "c1: edit b"
git -C "$B" fetch -q origin
git -C "$B" checkout -q -b feat origin/main
sed -i '1s/.*/c2/' "$A/a.txt"
a_commit "c2: edit a"
sed -i '3s/.*/3staged/' "$B/a.txt"
git -C "$B" add a.txt
sed -i '3s/.*/3wt/' "$B/a.txt"
echo wip >> "$B/b.txt"
before=$(b_head)
run_pull
check "15 refused checkout: exit 3" test "$RC" -eq 3
check "15 refused checkout: says checkout failed" out_has "git checkout main failed"
check "15 refused checkout: HEAD unchanged" test "$(b_head)" = "$before"
check "15 refused checkout: still on feat" test "$(git -C "$B" branch --show-current)" = feat
check "15 refused checkout: overlap file dirty again with its edit" test "$(sed -n 3p "$B/a.txt")" = 3wt
check "15 refused checkout: staged version back in the index" test "$(git -C "$B" show :a.txt | sed -n 3p)" = 3staged
check "15 refused checkout: non-overlap edit kept" grep -qx wip "$B/b.txt"
check "15 staged patch carries the index version" grep -q '^+3staged' "$BK/_staged-clone-b-k.patch"
first_sum=$(sha256sum "$BK"/* | sort)
run_pull
check "15 retry with the same key: exit 3" test "$RC" -eq 3
check "15 retry with the same key: names the existing file" out_has "already exists"
check "15 retry with the same key: first backups byte-identical" test "$(sha256sum "$BK"/* | sort)" = "$first_sum"
check "15 retry with the same key: edits still in place" test "$(sed -n 3p "$B/a.txt")" = 3wt

scenario 16
echo SECRET > "$B/.cache"
echo ".cache" >> "$B/.git/info/exclude"
echo upstream > "$A/.cache"
a_commit "add .cache"
before=$(b_head)
run_pull
check "16 ignored clash: exit 3" test "$RC" -eq 3
check "16 ignored clash: lists the file" out_has ".cache"
check "16 ignored clash: HEAD unchanged" test "$(b_head)" = "$before"
check "16 ignored clash: file intact" grep -qx SECRET "$B/.cache"

scenario 17
git -C "$A" rm -q c.txt
a_commit "delete c"
echo more >> "$B/c.txt"
run_pull
check "17 upstream deleted a dirty file: exit 4" test "$RC" -eq 4
check "17 upstream deleted a dirty file: says apply failed" out_has "APPLY FAILED"
check "17 upstream deleted a dirty file: no empty marker list" bash -c '! grep -q "conflict markers in" <<<"$1"' _ "$OUT"
check "17 upstream deleted a dirty file: overlap patch kept" test -s "$BK/_overlap-clone-b-k.patch"

scenario 18
echo more >> "$A/c.txt"
a_commit "edit c"
rm "$B/c.txt"
run_pull
check "18 local deletion vs upstream edit: exit 4" test "$RC" -eq 4
check "18 local deletion vs upstream edit: report says what failed" bash -c 'grep -q "APPLY FAILED\|conflict markers in" <<<"$1"' _ "$OUT"
check "18 local deletion vs upstream edit: backup kept" test -s "$BK/_backup-clone-b-dirty-before-k-pull.patch"

scenario 19
sed -i '1s/.*/first/' "$A/a.txt"
a_commit "edit line 1"
git -C "$B" rm -q --cached a.txt
echo LOCALONLY >> "$B/a.txt"
before=$(b_head)
run_pull
check "19 out of the index, on disk: exit 3" test "$RC" -eq 3
check "19 out of the index, on disk: lists the file" out_has "a.txt"
check "19 out of the index, on disk: HEAD unchanged" test "$(b_head)" = "$before"
check "19 out of the index, on disk: local content intact" grep -qx LOCALONLY "$B/a.txt"

scenario 20
echo changed >> "$A/c.txt"
a_commit "edit c"
rm "$B/c.txt"
mkdir "$B/c.txt"
echo untracked > "$B/c.txt/u"
before=$(b_head)
run_pull
check "20 directory in place of a tracked file: exit 3" test "$RC" -eq 3
check "20 directory in place of a tracked file: lists the path" out_has "c.txt"
check "20 directory in place of a tracked file: HEAD unchanged" test "$(b_head)" = "$before"
check "20 directory in place of a tracked file: untracked file intact" grep -qx untracked "$B/c.txt/u"

scenario 21
printf '#!/bin/sh\ntr a-z A-Z < "$1"\n' > "$W/conv.sh"
echo '*.dat diff=up' > "$B/.git/info/attributes"
git -C "$B" config diff.up.textconv "sh $W/conv.sh"
seq -f 'line%g' 1 10 > "$A/d.dat"
a_commit "add d.dat"
git -C "$B" pull -q --ff-only origin main 2>/dev/null
sed -i '1s/.*/first/' "$A/d.dat"
a_commit "edit d.dat line 1"
sed -i '10s/.*/last/' "$B/d.dat"
before=$(b_head)
run_pull
check "21 textconv driver: exit 0" test "$RC" -eq 0
check "21 textconv driver: HEAD == origin" test "$(b_head)" = "$(origin_head)"
check "21 textconv driver: pulled change on disk" test "$(sed -n 1p "$B/d.dat")" = first
check "21 textconv driver: local edit on disk, not uppercased" test "$(sed -n 10p "$B/d.dat")" = last
git clone -q "$B" "$W/scratch" 2>/dev/null
git -C "$W/scratch" checkout -q "$before"
check "21 textconv driver: backup patch applies to the old HEAD" \
  git -C "$W/scratch" apply --check "$BK/_backup-clone-b-dirty-before-k-pull.patch"

scenario 22
mkdir "$A/d"
seq 1 10 > "$A/d/file"
seq 1 10 > "$A/file"
a_commit "add d/file and file"
git -C "$B" pull -q --ff-only origin main 2>/dev/null
git -C "$B" config diff.noprefix true
sed -i '1s/.*/first/' "$A/d/file"
a_commit "edit d/file line 1"
sed -i '10s/.*/last/' "$B/d/file"
run_pull
check "22 diff.noprefix: exit 0" test "$RC" -eq 0
check "22 diff.noprefix: d/file has the pulled change" test "$(sed -n 1p "$B/d/file")" = first
check "22 diff.noprefix: d/file has the local edit" test "$(sed -n 10p "$B/d/file")" = last
check "22 diff.noprefix: root file unchanged" test "$(cat "$B/file")" = "$(seq 1 10)"
check "22 diff.noprefix: backup patch uses a/ and b/ prefixes" grep -q '^--- a/d/file' "$BK/_backup-clone-b-dirty-before-k-pull.patch"

[ "$fail" -eq 0 ] && echo "all green"
exit "$fail"
