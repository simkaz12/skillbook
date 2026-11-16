---
title: Delegation tiers
covers: agent/*, doc/GLOBAL-CLAUDE.md, hooks/load-agent-additions.sh, hooks/load-tabularium-role-context.sh
---

Main talks to the owner and dispatches. Agents do the work. The first section of the global `CLAUDE.md` says so in one table, and every other skill assumes it.

## The rule

There are four tiers, and one more reviewer that is not a tier.

- Main (Opus) owns the conversation, grilling, specs, dispatch and the synthesis of what comes back. It never edits code, never drives Playwright and never reads or greps at scale. The one exception is a trivial single-file edit the owner asks for inline.
- `hand-ex` (Sonnet) is a read-only explorer. It traces real code and data flow, reproduces bugs in a browser and returns verified findings. It cannot edit.
- `hand-do` (Sonnet) builds one bounded brief, tests it with the project's own commands and returns a verdict. It never commits.
- `bolt` (Haiku) answers one narrow factual question per dispatch. Several can run at once. When a question needs more than one hop it says "needs a hand-ex" instead of guessing.
- Codex (GPT) is the cross-model reviewer. Main does not run the review. `hand-do` and `spec-runner` run it themselves at the end of their work.

`spec-runner` and `spec-reviewer` are the pair that executes and then gates a `to-spec` brief. The runner writes and never judges its own diff. The reviewer judges and never writes.

When Codex is main, main, both hands and the spec roles use the latest Sol with high reasoning; `bolt` uses the latest Luna. `CODEX-TAIL.md` holds that policy. The `sol` and `luna` source selectors resolve to real model IDs from the visible Codex catalog when `bash scripts/sync-codex.sh --agents-only` regenerates the rules and agent files. Refresh the Codex catalog before syncing, then reload Codex to load the new native roles. Sync leaves skill links, hooks and the main session's model setting alone. For T3 dispatch, discover the provider's available models and select the highest numeric version within the exact Sol or Luna family. Set `target.model` explicitly and `target.options.reasoningEffort` to `high` for Sol. A running main keeps its current model; choose the latest Sol when starting or configuring it.

## Why

Main's context is the scarce part. It holds the conversation and the settled agreement, and a grep over a large repository spends that room on text nobody has judged yet. Routing reads to `bolt` and `hand-ex` and writes to `hand-do` keeps main small enough to remember what was agreed.

The Codex gate sits inside `hand-do` for a locality reason. When the gate is behind the agent's own interface, no dispatcher has to remember the gate rule, and the rule lives in one agent file. Two alternatives were rejected. One was trusting main to remember to run the review, which was the original leaky design. The other was a hook that reminds or blocks, which patches the seam in the wrong place.

## Tools as policy

The memory store has no agent-facing write tool. Agents get `recall`, and `decisions_query` and `decision` where they gate work against locked decisions. The only write path is `memory_propose`, which queues a tile that persists only after the owner approves it, except a defect, which saves at once as an open defect unless it carries `closes` or lands near an existing record. The owner keeps the final call on facts and decisions. Agents put findings in their verdict, and main proposes what survives.

A prohibition written without an alternative is where agents start improvising. Briefs state both halves: you have no write tool for the store, by design, so put it in your verdict.

## Project differences

A base agent never names a project. Per-project behaviour lives in `agent-projects/<key>/<agent>.md` and is injected when the agent starts, by a `SubagentStart` hook. A second hook injects role-specific memory. The two are separate on purpose, so a memory outage cannot stop project additions from loading. See [Config as repo](#/principle/config-as-repo) for the layering and [Memory](#/principle/memory) for the role grounding.
