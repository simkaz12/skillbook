---
name: flow
description: Keeps one piece of work moving through only the investigation, agreement, brief, execution, review, verification and landing it still needs, carrying settled understanding across handoffs. Use when the owner says flow, continue flow, or wants a ticket or mapped effort to stop repeating discovery between skills.
allowed-tools: Bash(*/skill-project.sh *)
---

# Flow

`flow` is an owner-directed coordinator, not a replacement for `recon`, `grill-me`, or `to-spec`. Keep the active work state in the conversation: what is evidenced, what is agreed, what is uncertain, and the current report, map, or brief. Do not create a second ledger.

On `flow` or `continue flow`, start from memory before choosing anything: call `memory_recall` with `audience: "decider"` for the piece. Before anything else, run `bash ~/.claude/skills/../scripts/pull-base.sh --no-switch` in the repo, and in its partner when the piece spans both. This is the piece's only pull; `verify-ticket` run from flow skips its own. On `continue flow <key>`, find the piece's brief, recon report or map: when `<key>` names a brief (`2026-10-12-foo.md`, or `docs/specs/2026-10-12-foo.md`), strip the directory and `.md`, then look for the file in `docs/specs/` or `~/.claude/specs/` and read it with its first heading. A ticket in the name or the heading is the key; otherwise the key is the name without its leading date, here `foo`. That file is the working artifact. Then call `memory_recall` with `audience: "decider"` for the piece by ticket or name in the scope for its decisions; only when `memory_recall` is not in the tool list, fall back to `mcp__tabularium-mcp__recall` and `mcp__tabularium-mcp__decisions_query`. Do not rediscover what the brief and those records already settled. On `continue flow`, call the `ListAgents` tool first; a live runner on the same brief is resumed, not redispatched.

At each turn, choose the smallest next activity that removes a named uncertainty:

- A missing fact calls for a focused trace. Ask one bounded investigation with the report or brief path and the established facts its question builds on; Project additions may name the skill to use.
- A product choice or non-derivable expectation calls for `grill-me`. Never treat silence as approval.
- Settled behavior and constraints call for `to-spec`. It formats and divides the agreement; it does not rediscover it.
- A completed brief calls for fresh, bounded `spec-runner` and `spec-reviewer` windows when the owner has already authorized implementation. They judge independently, but begin from the same agreement and linked evidence. Every implemented piece with reviewer PASS routes to `verify-ticket` before done, map close, or shipping, using the project's applicable acceptance checks. Any product edit after a `verify-ticket` PASS, a fix or an added scope, reruns the affected proof before the piece is reported done.
- A failed runner, reviewer, or verification verdict returns to the smallest gap: an authorized local implementation correction, a missing fact, or a decision that must reopen. Do not restart every earlier activity. A doer verdict that reports a brief check as not met (a static-analysis count above baseline, a red focused test, an unrun Verify) goes straight back to the doer; do not spend a review round confirming it. Either review loop stops at round 4; hand the open `must_fix` to the owner. When a run reopens a decision, amend the brief in place: revise the decision with its rationale, add a one-line run history, mark done scopes, and rewrite every Out of scope, Done or caveat line the change contradicts; a runner reads a stale line as a fence. A direct verification request goes straight to `verify-ticket` from current evidence.
- A tester's bounce on an implemented ticket is a failed verification of the whole ticket. The tester reports the first blocker on one path, so measure the smallest gap against the ticket's full acceptance list, and count every criterion nobody has exercised end to end as a gap. Before recon, grill or brief on a bug or a bounce, run `verify-ticket`'s failure check (its `Bug or bounce` section). A claim that does not reproduce stops the piece and goes to the owner. The `Failure evidence` names what the bounced field or feature is for, and the trace follows that effect end to end; the bounce's framing ("a small validation issue") does not narrow it. The brief links the `Failure evidence`.
- Settled ticket work goes to `to-spec` even when the fix is one line; a small brief stays small. Do not offer to skip the brief. A FAIL goes back to the `hand-do` with the `must_fix`. Its dispatch prompt may rule a layer out only on `[ran]` evidence; a `[read]` claim that another layer needs no change goes to the hand as a question, not a fence.
- Owner feedback on an open PR is a change to the same piece of work, not a new one. Make the fix on that piece's own branch or worktree, re-run only the reviewer and `verify-ticket` checks it touches, then `land` it onto the same branch. Before reporting a PR as awaiting merge, run `git status` in its worktree. A dirty tree means the fix has not reached the PR.

There are two shapes:

- **Bounded ticket:** orient, investigate only named gaps, grill only unresolved expectations, then brief, run, review, and verify.
- **Larger effort:** the owner plans the map with `wayfinder` before invoking `flow`; `flow` never runs `wayfinder` itself. Take one executable piece from the map and work it through grills and briefs. After a piece completes, note what changed in the brief or the map, and leave any replanning of the map to the owner.

Direct use of the named skills remains valid. Do not force this coordinator onto unrelated work. Use `flow-eval` only when comparing workflow variants.

## Quick fix

An owner-triggered exception for one-shots outside any ticket: pulling data, a small mix-up. It starts only when the owner says "quick fix"; main never proposes it. Exclusions, each of which sends the work back to the normal route: a migration, a new route, a permission or auth change, a new dependency. Main edits inline, then dispatches one `hand-ex` that observes the stated result on the real surface, runs the focused tests, and writes `docs/qa/<date>/quick-<slug>.md` (crm) or `docs/verification/quick-<slug>.md` (elsewhere) with what changed, what was observed, and which files. The agreement it checks is the owner's one-line ask. No `spec-reviewer`, no branch, no commit, no `land`, no Jira; the owner handles git. The quick fix ends when the note is written.

## Project additions

!`$HOME/.claude/skills/../scripts/skill-project.sh flow`

If the line above shows a raw command instead of content, run it.
