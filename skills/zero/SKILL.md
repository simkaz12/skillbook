---
name: zero
description: Land plus merge, pull and rebuild for the owner's personal repos. Takes finished work through commit and PR the way land does, with or without a verify-ticket proof, then merges the PR, pulls the build branch and rebuilds or deploys what the repo ships. Use when the owner says "zero", "zero it", "zero this repo", or /zero in a repo whose origin is the owner's personal GitHub account. Never runs in client work repos. Ticket work in other repos goes through land.
allowed-tools: Bash(*/skill-project.sh *)
---

# Zero

Land plus merge, pull and rebuild. One call takes the finished piece from the working tree to a merged PR, a current build branch and a rebuilt app. Every step can be reverted, and zero runs through without a confirmation turn.

## Hard stops

Check this before anything else. Lowercase the repo's top-level directory name (the main checkout's, inside a worktree) and the `origin` URL. If either contains a client project name (for example `crm`), refuse with one line that names the repo and points to `land`: "zero does not run in <repo>; use land." There is no override, even for a fork under the owner's account.

## Gate

`git remote get-url origin` must point at `github.com/<owner>/` (SSH or HTTPS). Anything else gets refused: "zero is for personal repos only." There is no override.

A personal repo with no zero project file has no known build branch or rebuild step. Ask the owner for both and stop until they answer.

## Project additions

Land's section is the source for branch naming, commit subject, PR conventions (`--repo`, body), mechanical proof, proof path, live hooks and the skillbook worktree rule:

!`$HOME/.claude/skills/../scripts/skill-project.sh land`

Zero's section holds only what land lacks, the build branch (the PR base), the merge method and the rebuild step:

!`$HOME/.claude/skills/../scripts/skill-project.sh zero`

If either line above shows a raw command instead of content, run it.

## Land steps

Follow `land` by section name, in its order, with the land project additions above: **Read the state**, **Select and split**, **Exclude the scaffolding**, **Prototypes**, **Repos**, **Commit message**, **PR body** and **After the PR**. Skip the last paragraph of **After the PR**, the switch back to base, which Pull below replaces. **Defects** and **Harvest** run after Rebuild.

- **Selection.** Only this piece's files go in, never every dirty file. The set comes from the brief's Files; with no brief, from the files this thread changed, without land's wait for the owner. A dirty path outside the set stays on disk and goes in the report as left out. If you can't tell whether a file belongs, leave it out and name it.
- **Proof is optional.** If a `verify-ticket` proof exists at the path land's section names, recompute its fingerprint with the command the artifact records and report whether it matches. A missing or stale proof never blocks.
- **Mechanical proofs and hooks still block.** Run the mechanical proof from land's section before committing. A failed proof or pre-commit hook stops the run.
- **No full-suite wait.** Skip land's full-suite paragraph and `test-baseline.py`.
- **Push.** Push with `git push -u origin <branch>`, so the branch tracks its remote and `git branch -d` can delete it after the merge.
- **PR number.** Keep `<n>` from the `gh pr create` output. With `--repo`, gh takes no PR from the current branch, so every `gh pr` call in Merge and Pull needs the number.
- **Thread link.** Link the PR to the thread when the T3 tools are present.

## Already landed

Before cutting a branch, look for an open PR into the build branch that already carries the work. A PR belongs to this piece only if it is linked to this thread, or HEAD is its head branch. List the open ones with `gh pr list --repo <owner>/<repo> --author @me --base <build branch> --state open --json number,headRefName` and check each against those two.

Exactly one belongs: keep its number `<n>`, skip PR creation, report the proof status and what stays on disk, and run the two checks below, in order, before Merge. Two or more belong: ask the owner which. None belongs: open a new PR through the land steps. Never merge an open PR that does not belong, a lone one by `@me` included.

The checks apply to a picked-up PR only. A PR zero created in this run carries its selection by construction. That matters in skillbook, where a partial-file selection goes in by patch and leaves the other hunks in the live file.

Start with `git fetch origin <headRefName>`.

**Unpushed commits.** Only when HEAD is the PR's head branch: compare `git rev-parse <branch>` with `headRefOid` from `gh pr view <n> --repo <owner>/<repo> --json headRefOid`. If they differ, check that the local commits the PR head lacks (`git log <headRefOid>..<branch>`) belong to this piece. If they do, run `git push -u origin <branch>` and read `headRefOid` again. If they do not, or the PR head holds commits the local branch lacks, ask the owner. Never push before that ownership check. Never merge while the local tip is ahead of the PR head.

**Dirty.** Evaluate this on what remains. For each selected file, compare `git rev-parse -q --verify origin/<headRefName>:<file>`, the PR's blob, with `git hash-object <file>`, the content on disk. Both missing (deleted in the PR and gone on disk) is clean. Equal hashes are clean. Anything else is dirty. A file that matches the PR is clean even when `git status` lists it: in skillbook the live checkout keeps the landed files modified, or untracked when new, on `master` until the pull after the merge, so a `git status` test would ask every time.

If any selected file is dirty, the PR does not yet carry the whole piece. When HEAD is the PR's head branch, commit those files as a follow-up commit on that branch under land's selection and commit message rules, with the mechanical proof and hooks above, and run `git push -u origin <branch>`. Otherwise ask the owner. A partial-file selection in skillbook reads as dirty on a pickup, so it asks.

## Stop

| Condition | Response |
|---|---|
| Rebase, merge, cherry-pick or bisect in progress | Report the state and stop |
| Detached HEAD | Report the SHA and stop |
| HEAD is neither the build branch nor the head of an open PR into it | Report the branch and stop |
| Conflict markers in the selected files | Name the files and stop |
| Pre-commit hook or mechanical proof fails | Print its output and stop. Never `--no-verify`, never fix the lint and retry |
| Behind the build branch after `pull-base.sh --no-switch` | Report the count. The PR merges it. Never merge or rebase here |
| The branch's PR is already merged | Report and stop. Cut a new branch from the build branch |
| No file can be tied to this piece | Ask which files and stop |
| On a picked-up PR, selected files are dirty (as defined in Already landed) and HEAD is not its head branch, or the tips differ and the local commits are not this piece's | Ask the owner and stop |
| PR reads `CONFLICTING`, still reads `UNKNOWN` after the mergeable wait, a reported check fails, or `gh pr merge` refuses | Report and stop. Leave the PR open |
| `pull-base.sh` exits 3 or 4 | Print its report and stop |

## Merge

Use the PR number `<n>` from `gh pr create` or the pickup lookup. With `--repo`, gh refuses both commands below unless the number is given.

If checks are reported, wait for them (`gh pr checks <n> --watch --repo <owner>/<repo>`). A PR with no reported checks has nothing to wait for.

Then poll an open PR with `gh pr view <n> --repo <owner>/<repo> --json mergeable -q .mergeable` every few seconds, for about 30 s at most, until it reads `MERGEABLE` or `CONFLICTING`. `CONFLICTING` hits the Stop row. Still `UNKNOWN` at the cap: report, stop and leave the PR open. Poll only an open PR; on a merged one `mergeable` reads `UNKNOWN`.

Then run `gh pr merge <n> --repo <owner>/<repo>` with the merge method from zero's section. The default is `--merge`. Never use `--rebase`.

## Pull

Switch to the build branch and run `bash ~/.claude/skills/../scripts/pull-base.sh`. It is the only pull here: it backs up overlapping dirty files and reapplies them, which `git pull --ff-only` cannot do. If the switch refuses because a tracked change would be overwritten, report it and leave the tree where it is. This replaces land's switch-back step and any `git pull --ff-only` in a project file.

Then delete the merged branch where it exists. Run `git branch -d <branch>` first, while its upstream ref is still there. Then run `git push origin --delete <branch>`; the remote delete runs whether or not `-d` worked.

If `-d` refused ("not fully merged", as after a `--squash` merge or a branch with no upstream), run `gh pr view <n> --repo <owner>/<repo> --json state,headRefOid`. Delete the local branch with `git branch -D <branch>`, after the remote delete, only when `state` is `MERGED` and `git rev-parse <branch>` equals `headRefOid`. Otherwise a local commit made after the last push would be lost: report the refusal, name the branch and leave it. `-D` is allowed only here.

## Rebuild

Run the rebuild step from zero's section. Long builds and deploys run in the background; wait for them, then check that the build left no new changes in the tree beyond the leftovers already named. A build that writes into tracked files gets reported, not committed. A repo with no rebuild step ends at the pull.

## Close out

Run land's **Defects**, then **Harvest**. A run that stops before the merge skips Defects, so no defect closes ahead of its fix, and still runs Harvest.

## Never

Land's **Never** applies in full, including nothing under `docs/` in a commit or PR and no silent skip of the harvest. Also never:

- stash, push to `upstream`, or commit with `--no-verify`
- `git branch -D`, except in Pull when `-d` refused, the PR reads `MERGED` and the branch tip equals its `headRefOid`
- merge a picked-up PR while a selected file is dirty (as defined in Already landed), or while the local tip is ahead of the PR head
- `gh pr merge --rebase`
- stage `.env` or `.env.*` (a tracked `.env.example` aside), or anything else that holds a secret

## Report

```
## Zero — t3code / city-backgrounds
proof    verify-ticket PASS @ 8f2a1c4, fingerprint matches
commit   fix(web): city 783 composer edge   6 files  +412 -14
pr       #1 https://github.com/<owner>/t3code/pull/1   merged d424eca222
left out .env, docs/specs/2026-10-22-composer.md, apps/web/src/draft.ts (dirty, not this piece)
deleted  COMPOSER-CHECK.md
pull     pull-base fast-forwarded dev, 2 dirty files reapplied
branch   dev @ d424eca222, matches origin
rebuild  release/T3-Code-0.1.0-x64.tar.gz staged at ~/.local/opt/t3code-fork.new
defects  closed 1, released 0
harvest  2 proposals
next     quit T3 Code, run the swap line below, relaunch
```

`proof` reads `none` or `stale` when there is no match, and adds the mechanical proof result for a repo that has one. A picked-up PR replaces `commit` with `already open` and shows no new commit. `defects` appears only when the brief took defects, and `harvest` always appears.
