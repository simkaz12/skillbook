---
name: land
description: Lands finished work in git — commit, push, PR in the repo's own convention, gated on a current /verify-ticket proof. Use on "land", "land this", /land, or any request to commit, push, or open a PR for verified work.
allowed-tools: Bash(*/skill-project.sh *), Bash(*/test-baseline.py *)
---

# Land

## Authority

Offer, never act. Reaching this skill on your own initiative produces a proposal in text and nothing else — no staging, no commit.

Acting is tiered by repo:

- **crm-api, crm-web, arx, skillbook, Tabularium, t3code** — run through without a confirmation turn: commit, push, PR. Project additions can add steps to the run-through.
- **Any other repo** — refuse. "No convention on file for this repo." Never guess a convention from a dirty tree.

Running through is not running blind. The gate below still holds, the selection still comes from the brief, and anything the run-through decides on its own — a base branch that is not the repo's default, a file whose status is unclear — gets named in the report rather than buried. Stop and ask only where a choice is genuinely the owner's: which branch a stacked PR targets, or a `Stop` row firing.

When the owner asks for a plan first, show one: the commit message, the files, the file count, and the line delta as `+n/-n`.

## Project additions

!`$HOME/.claude/skills/../scripts/skill-project.sh land`

If the line above shows a raw command instead of content, run it.

Per-repo data referenced below lives here: the proof path, mechanical proofs, live hooks, the repo table row, base branch, reviewer, and any post-PR steps.

## Precondition

`verify-ticket` must have proven this work. Read its artifact and compare the recorded revision and fingerprint against what is about to be committed. A mismatch means the proof is stale: refuse, and name the file that moved since `verify-ticket` passed. Recompute the fingerprint with the command the artifact records; never with a command of your own. Also refuse a PASS when a criterion row's `Conditions` is not `reporter` and no owner waiver in the artifact names that row. Name the row. A proof with no `Conditions` column is treated the same way.

The artifact is `docs/verification/<slug>.md` by default. The proof path can differ per repo, and Project additions name it; an empty `docs/verification/` is not a missing proof where another path is named. Since several repos run through without a confirmation turn, this gate is the only thing standing between an unverified diff and a pushed branch. Look in the right place before refusing.

A repo with no drivable surface for `verify-ticket` may name a mechanical proof in Project additions instead. A failure there stops the commit exactly as a stale proof does.

**Full suite.** For a repo named in a `testing.md` (`agent-projects/<scope>/testing.md`), run `python3 "$HOME/.claude/skills/../scripts/test-baseline.py" wait .` from the tree being landed, in the background with the Bash tool, and wait for it. The reviewer started this run at PASS, so it is usually finished; when it is still going, say so and wait. `test-baseline.py wait` exiting 0 proceeds. Exit 1 stops: print the report and name each line under `NEW FAILURES`. Exit 2 stops with the stderr line. There is no override inside this skill. A repo with no `testing.md` section, or whose section has no `full:` line (crm, owner ruling 2026-11-03: focused tests plus the reviewer's gate are the bar), skips this step and the report says `suite    none configured`. A flaky result on a tree that has not changed reruns with `test-baseline.py start --rerun .` then `wait .`; `wait` alone reuses the last compare.

The owner can override by saying so in that turn. The override goes in the report.

## Read the state

First run `bash ~/.claude/skills/../scripts/pull-base.sh --no-switch` in the repo. On the base branch it brings the base up to date, so the branch you cut next starts from the latest base. On any other branch it fast-forwards the local base ref without checking it out or touching a file, and prints how far the branch is behind.

```
bash ~/.claude/skills/land/land-state.sh
```

Repo, branch, host, upstream, ahead/behind, in-progress operation, tracked and staged changes, untracked files, risky paths, recent subjects, open PR. Never route from an earlier `git status`; the tree moves underneath you.

## Stop

| Condition | Response |
|---|---|
| Rebase, merge, cherry-pick, or bisect in progress | Report the state and stop. Repair is its own task |
| Detached HEAD | Report the SHA and stop |
| Conflict markers in the selected files | Name the files and stop |
| Pre-commit hook fails | Print its output and stop. Never `--no-verify`, never fix the lint and retry |
| `verify-ticket` proof missing or stale | Refuse, unless overridden in the turn |
| PASS proof with an unwaived non-`reporter` row | Refuse and name the row |
| Full suite reports new failures or an error | Print the report and stop. The fix is a change to the piece, not a land option |
| Behind base after `pull-base.sh --no-switch` | Report the count. The PR merges it. Never merge or rebase here |
| The branch's PR is already merged | Report and stop. A commit pushed there is stranded. Cut a new branch from base |

Worktrees are normal operation here, not a stop condition. Report which one you are in.

Live hooks differ per repo; Project additions name them.

## Select and split

The brief is the authority. `to-spec` writes it to `<repo>/docs/specs/YYYY-MM-DD-<slug>.md`, or to `~/.claude/specs/YYYY-MM-DD-<slug>.md` for global and cross-repo work. Take the path from the conversation; ask for it when there is none.

Each scope carries **Files** (exact Create, Modify, Delete paths) and **Blocks**. Those are the selection and the order: one commit per scope, each following whatever it blocks on, all on one branch under one PR. Scopes never become separate branches or separate PRs.

Never infer the file set from the working tree. Every one of these repos carries unrelated dirty changes, and sweeping them in destroys work you did not write. A path that is dirty in the tree but absent from the brief's Files stays out of the commit — name it in the report instead.

Without a brief, show the plan and wait for the owner; the run-through applies only to brief-selected files.

Stage by path, every time.

## Exclude the scaffolding

Work leaves artifacts that are not the work. They stay out of the commit and get named in the report:

- prototypes and review pages built to look at the change
- plans, notes, and write-ups that were thinking rather than deliverable
- playwright screenshots, `.playwright-mcp/` dumps, files a subagent dropped at the repo root
- untracked files that appeared at the repo root during the work

`docs/specs/` and `docs/verification/` are never committed and never deleted.

When a file's status is unclear, exclude it. An excluded file is still sitting on disk; a committed one is in history.

## Prototypes

Move a prototype built to review the change to `/tmp/land/<repo>/` and report the destination. This covers review pages, mockups, scratch HTML, and throwaway scripts written to look at something.

## Repos

Project additions give the row for this repo, with these columns: Branch (naming rule), Subject (commit subject convention), Ends at (the PR base), Reviewer.

The base branch is not guessable and `origin/HEAD` can be stale. Check Project additions for it; never read it from `origin/HEAD`.

Project additions may also give the commit subject rule, the reviewer account, and what landing does or does not deploy.

Set the reviewer in the same command that opens the PR, so a forgotten reviewer cannot survive the run-through, then confirm the request landed.

When the work is already sitting on the repo's base branch and that repo ends at a PR, cut the branch before committing — `git checkout -b <derived name>` carries uncommitted work across untouched. Never commit onto the base and open the PR afterwards.

## Commit message

Short. The repo's own convention from the table, not a house style carried in from elsewhere.

A body only when the change has a reason the diff cannot show, and then it explains why rather than what.

A repo's Project additions may rule out a commit or PR body entirely.

## PR body

Small. The reviewer reads the diff; the body carries only what the diff cannot say for itself. Two or three lines, six at the outside. A repo whose Project additions rule out a body gets none.

What earns a line:

- one sentence on the shape of the change
- a reason the diff cannot show
- the pointers that repo already uses — brief and verification paths on Tabularium, card path on arx, `Follow-up to #n` on a review-fix branch

What does not: `## Problem` and `## Changes` headings, a file-by-file inventory, a bullet per hunk, a walkthrough of what the code now does. The brief and the verification artifact already hold all of that, and the body reaches them in one line. Writing it out twice means the PR and the artifact drift apart.

```
Follow-up to #34. When the family-event write fails after `ledger.dispatch` has already started the reviewer, the hand is never cancelled and its container can outlive arx.

**Card:** docs/wayfinder/maps/arx-reliability/R18-record-family-after-reviewer-spawn.md
```

Past PRs in these repos run far longer than this. They are not the convention to copy.

## After the PR

If Project additions define post-PR steps, run them after the PR is open.

Then dispose of everything the filter held back:

- **Tool debris** — playwright screenshots, `.playwright-mcp/` dumps, stray images and report files a subagent left behind. Delete them, naming each path as you go.
- **Prototypes** — move to `/tmp/land/<repo>/` per the section above.
- **Anything you cannot place** — leave it alone and name it.

Last, go back to the base branch the PR ends at, from Project additions: `git switch <base>`, then `bash ~/.claude/skills/../scripts/pull-base.sh`. The landed branch stays on the remote for the PR. Uncommitted files ride across the switch untouched. If the switch refuses because a tracked change would be overwritten, or the pull cannot fast-forward, report it and leave the tree where it is. Never stash, merge, or rebase to get there.

## Defects

Run before the harvest. For every defect id the brief took with `memory_take`:

- Fixed by this land: call `memory_propose` with `closes: <recordId>`. The claim names the test or diff that proves the fix.
- Not fixed: call `memory_release` and give the reason in the report.

A brief that took no defects skips this section.

## Harvest

Run this last, after the PR is open and the steps above are done. A repo whose convention has no PR runs it after the push.

1. Call `memory_harvest_begin` first. It stamps a checkpoint for this thread and returns `afterPosition`, `since` and `threadId`.
2. Read the span with `t3_thread_read`, passing `afterPosition` and `view: "activity"`, which carries tool calls. Follow `nextPosition` until the read ends. If the span contains a `memory_propose` call, the thread proposed inline: report `harvest: skipped, proposed inline` and stop.
3. Otherwise read the same span with `view: "messages"` to find what is worth proposing.
4. Call `memory_propose` with `origin: "harvest"`, once per decision, gotcha or defect in that span. Five proposals at most.

Rules for the proposals:

- Skip anything `memory_recall` already holds and anything this thread already proposed.
- Keep each headline under 100 characters; it is the claim in one sentence.
- The thread excerpt carries the reason, so the proposal has no field for it. Keep ticket ids, dates and commits out of the claim.
- A decision carries the alternative the owner ruled out, in `rejected`.
- Never propose status or session narrative. The commit and the PR already record what shipped.

A span with nothing durable yields no proposals. Say so in one line.

If the memory tools are not available, because the skill is running outside t3 or the tools answer that memory is not configured, say so in one line and finish the land. The harvest never blocks or fails a land. When a harvest call errors, report the error once and move on. Never retry in a loop.

## Never

Never add /docs to the pr or a commit.

Never skip the harvest silently. The report always says whether it ran and how many proposals it made, or that it was skipped because the thread proposed inline.

Rebase. `push --force` in any form. `reset --hard`. `clean`. `checkout -- .`. Amending a pushed commit. `add -A` or `add .`.

These have no override inside this skill. If the owner wants one, it happens as an ordinary request outside `/land`.

## Report

```
## Land — arx / r19/e04-ledger-guard
verify-ticket PASS @ 8f2a1c4, fingerprint matches
suite    clean @ run 3f9c1a2, merge-base a1b2c3d
commits  2
         r19-ledger-guard: reject unsigned entries   4 files  +118 -12
         r19-ledger-guard: cover the replay path     2 files  +64  -0
push     origin/r19/e04-ledger-guard
pr       #88 https://github.com/<owner>/arx/pull/88   reviewer: none (arx)
tree     clean
branch   back on main @ 3d91e07
defects  closed 1, released 0
harvest  2 proposals
```

Report each post-PR step from Project additions as its own line between `pr` and `tree`. A repo with no `testing.md` section, or no `full:` line in it, reports `suite    none configured` on the same line.

The report carries a `defects` line (`closed <n>, released <m>`) when the brief took defects, and ends with a `harvest` line giving the proposal count, `skipped, proposed inline`, or the one-line reason the harvest did not run.

`tree` must read clean before this reports done. Work left behind after a push is stranded: the PR merges without it and the branch is deleted around it.
