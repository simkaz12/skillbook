# Skills index

Map of the personal skills under `~/.claude/skills/`. The buckets below are **conceptual** — on disk every skill is a flat, direct child of this directory.

**Why flat:** Claude Code discovers personal skills exactly one level deep (`~/.claude/skills/<name>/SKILL.md`) and the invocable name comes from the *directory name*, not the frontmatter. Nesting a skill under a category folder (`skills/engineering/diagnose/`) hides it from discovery. Matt Pocock's source repo nests for human browsing; the installed layout must be flat. So this file is the category map, not the filesystem.

**Notation:** a leading `/` means the skill is **slash-only** (`disable-model-invocation: true`) — it never fires on its own and must be invoked explicitly. Everything else can also self-trigger on its description.

---

## Which planning skill when?

Start by closing understanding, then pick an executor by size and shape.

```
Want one active thread to choose only the next needed step? .. flow

Fresh Jira ticket, haven't read it yet? ........ recon <n>  (read-only scope, then ↓)

Do you understand the problem well enough to build?
├─ No, stress-test it in conversation only ............. grill-me
└─ No, AND capture the domain model durably
     (glossary → CONTEXT.md, hard calls → docs/adr/) .... grill-with-docs

Once the design is agreed, how big is the work?
├─ Solo, scope-sequential work ......................... to-spec ──▶ solo brief ──▶ spec-runner ──▶ spec-reviewer ──▶ verify-ticket
├─ Big, with independent scopes ........................ to-spec ──▶ split brief ──▶ spec-runner lanes ──▶ integrate ──▶ spec-reviewer ──▶ verify-ticket
└─ Open-ended decision territory ....................... /wayfinder  (decision tickets, resolved one at a time)
```

Two execution shapes ship from the same front door: **solo** (`to-spec` writes the brief, one `spec-runner` implements it, `spec-reviewer` gates it) and **split** (same brief plus a `## Dispatch plan`; main dispatches one `spec-runner` per lane in waves, an integrate-mode `spec-runner` runs the build and the cross-scope checks; `verify-ticket` owns the full suite, `spec-reviewer` runs the one codex review and gates it). `flow` keeps the agreement through the handoffs; fresh runner and reviewer windows stay bounded. The kanban loop was dropped 2026-08-20 and the gauntlet 2026-09-07; see **Removed** below.

---

## Plan & design

- **flow** — keeps a bounded ticket or a larger map effort in one active thread, choosing only the next needed investigation, grill, brief, execution, review, or verification. It carries settled agreement through real handoffs; direct use of its named skills still works.
- **recon** — progressive read-only scope of one Jira ticket: orient, trace one named gap, then expand only when the evidence requires it. Writes `docs/recon/PROJ-<n>.md`; never edits code or transitions Jira.
- **grill-me** — interview to reach shared understanding and state the behavior, decisions, constraints, and evidence that the brief inherits.
- **grill-with-docs** — grill *and* write it down: glossary terms to `CONTEXT.md`, hard-to-reverse calls to `docs/adr/` + Tabularium.
- **to-spec** — turns settled agreement into a solo or split execution brief without rediscovery, or routes genuinely open decision territory into `/wayfinder`.
- **/wayfinder** — plan work too large for one agent session as a map of decision tickets, resolved one at a time until the route is clear.

## Build

- **/improve-codebase-architecture** — find deepening opportunities in a scoped subsystem and propose refactors.
- **typesafe-ai** — design guidance for building on TypeSafe's Jev (Choice / Noul / Score over one state), deferring every API fact to the live docs at docs.typesafe.ai. Vendored word-for-word from `typesafe-ai/skills` v0.5.7 (`65a39f3`, MIT); do not edit locally, re-copy on upstream change.

## Review & verify

- **/review-structure** — explorer (not gate) for structural review of a diff/branch/PR, findings named in mattpocock vocab.
- **blast-radius** — what a change could break outside its own diff, proved by running real code; findings ranked on a five-rung certainty ladder where anything below "I ran it" must say so out loud.
- **preflight** — pre-handoff gate that drives the running app against the four slips a green suite hides; emits READY / NOT READY. Runs off the repo's verification map (`.claude/PW_CREDS.md` + `.claude/features/*.md`) and builds that map on first run in a repo that has none.
- **verify-ticket** — direct verification of an implemented ticket, agreed execution brief, or delivered change after review: one real acceptance check plus current project regression evidence. It reuses the locked agreement and existing proof instead of rebuilding a QA plan.
- **qa-ticket** — QA of teammates' tickets named by key: acceptance from the Jira description and comments, live proof by one `hand-ex` per batch, an artifact per ticket, then a fixed short pass comment and a move to `In verification`, or an owner-approved fail comment and a move to `Testing Failed`. The owner's own work stays with `verify-ticket`.
- **/how-to-test** — after preflight or matching `verify-ticket` evidence passes, turn the diff into a manual test plan for the human: each changed surface → its entry point → go/do/expect/watch. Writes steps for a person; never drives the app.
- **/debate** — two seats, `rune` (Claude, `hand-ex`) and `sol` (Codex `task`, read-only), hunt shortcomings in one subject across opening/rebuttal/closing rounds; main folds the closings into a ledger plus a verdict: fixes for agreed rows, settling checks for contested. No judge, nothing gets fixed.

## Diagnose

- **diagnose** — disciplined loop for hard bugs / perf regressions: reproduce → minimise → hypothesise → instrument → fix → regression-test.

## Meta & tooling

- **cleanup** — end-of-day sweep of finished local artifacts (playwright debris, drained plan-dirs, finished QA, their PRDs) across all repos: delete in work repos (to `.trash/`), archive in personal repos (to `docs/superpowers/backlog/`). Dry-run + confirm. Model-invocable — it can fire on its own, and the confirmation gate holds when it does.
- **/write-a-skill** — author or revise a skill as a deep module: a tight description over a lean SKILL.md, detail loaded on demand.
- **playwright** — browser verification in four tiers, from cheap CLI one-shots to interactive MCP debug.
- **reflect** — mine session transcripts for durable learnings and route each to a concrete edit on a skill that already exists; two read-only reviewers over the raw `.jsonl`, synthesis in main, no new place of truth.
- **flow-eval** — opt-in comparison of workflow variants on frozen cases. Use it when changing a flow, not on ordinary work.
- **/what** — stop, that last message did not land; re-pitch it.
- **zero** — land plus merge, pull and rebuild, for personal repos only. Lands the piece's files the way `land` does (verify-ticket proof optional, no full-suite wait), merges the PR on the fork, pulls the build branch with `pull-base.sh` and rebuilds or deploys per `skills/zero/projects/<key>.md`. Refuses in client work repos. Leftover dirty work stays on disk and is named in the report.
- **unslop** — editing pass that strips AI tells from a finished text and puts a human voice back in. The global rules apply the same list at write time; this is the deliberate rework. Derived from pstack (`cursor/plugins`, MIT), folded to the local fork (em-dash rule, jargon list, `LANGUAGE.md` exemption).

---

## Per-project additions

A skill can carry per-project deltas in `skills/<skill>/projects/<key>.md`, where `<key>` is a Tabularium scope (`crm`, shared by `crm-api` and `crm-web`) or a repo name (`crm-api`). A project gets the scope file first, then the repo file. They load under a `## Project additions` section at the end of the skill's SKILL.md (see the root README). `projects/` is a plain subdirectory of the skill, not a skill. Skills using it today: `flow`, `land`, `pi`, `playwright`, `qa-ticket`, `verify-ticket`, `zero`.

---

## Commands

Slash commands live in `~/.claude/commands/`, not here.

- **/flag**, **/good** — corpus-pipeline labels consumed by the capture hook; they produce no conversational output.

---

## Lifecycle

`in-progress` and `deprecated` are **tags noted here**, not directories (a skill dir can't carry a status without changing its name). When a skill is being reworked or retired, note it under this heading rather than moving its folder.

Nothing carries a tag right now.

## Removed 2026-09-07 — the gauntlet

- **gauntlet** — one builder plus two fresh-context critics per piece, up to three rounds. Two runs on client tickets showed the critic rounds spend far more than they catch. Replaced by the split brief: parallel `spec-runner` lanes, one codex review in `spec-reviewer` after integration.

## Removed 2026-08-20 — cold skills

Dropped on usage evidence (harness `skillUsage` counters over ~7 months): `review-gpt` and `triage` (zero invocations ever), `verification-before-completion` (1 use, 106 days prior), `prototype`, `tdd`, `teach` (1-3 uses, all >4 weeks cold), and `tester` (owner call). Dropping `tester` also retired the `qa-planner` / `qa-verifier` / `qa-fault-isolator` agent cluster, which nothing else dispatched. `diagnose-crash` was unlinked too — it was a symlink into `/usr/share/omarchy/default/agents/skills/`, placed by omarchy migration `1786539345.sh`; the distro copy is untouched and a future omarchy migration may re-create the link.

## Removed 2026-08-20 — the planning path

The kanban path went in one owner call: write-a-PRD, PRD-to-issues, driver, plus handoff. Reason
given: "they will need a rework and i prefer a clean slate." Driver had already been suspended
2026-08-18 ("i dont want to do driver loop, it needs fixing"), and the other two existed to feed it.
Retiring driver also retired the task-implementer and task-reviewer agents, which nothing else
dispatched; design-judge, figma-fetch and a screenshot helper went the same day for having no
dispatcher at all. The fleet is now bolt, hand-do, hand-ex, spec-runner, spec-reviewer.

Nothing writes a durable PRD today. Planning lands in one of two places: `to-spec` for work one
agent can hold, `/wayfinder` for work it can't.
