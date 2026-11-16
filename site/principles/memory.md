---
title: Memory
covers: skill/reflect, doc/GLOBAL-CORE.md, hooks/load-tabularium-context.sh, hooks/load-tabularium-role-context.sh, hooks/scope-map.sh
---

Claude Code starts every session empty. Skillbook keeps what should survive a session in Tabularium, a separate memory server that main reads on demand.

## The rule

Tabularium is the store. Nothing loads at session start, so no hook hands a session its memory. Main reads on demand: it calls `memory_recall` with the role's `audience` (decider, builder, reviewer or navigator) when prior decisions or gotchas bear on the task, and uses `recall` and `decisions_query` only as the fallback when `memory_recall` is not available. Tabularium v2 holds the live records. The Python v1 server is a read-only archive. The only write path is `memory_propose`, which queues a tile for the owner to approve, except a defect, which saves at once unless it carries `closes` or lands near an existing record. A scope is not the repository name. Two repositories can share one scope, so `hooks/scope-map.sh` maps a path to a scope and the hooks and scripts that need one use the same map.

Sub-agents get no memory payload from a hook. The `SubagentStart` hook loads the role's project additions, not records. A sub-agent recalls v2 itself, calling `memory_recall` with its own audience, and records with no audience come back for every role.

## Proposals and ids

`memory_propose` takes a `kind` (decision, fact or defect), a `headline` under 100 characters, a `claim`, for a decision the `rejected` alternative, and an optional `audience` (decider, builder, reviewer or navigator, or a free label on any kind). A defect adds its location fields, and the reason lives in the thread excerpt the tile carries. It holds gotchas and decisions, never status or session narrative. The response carries `flags`, what the checks found, and `neighbours`, the close saved records. Both are evidence for the caller. A fact or decision persists only when the owner approves its tile. A defect saves at once as an open defect, with no tile, unless it carries `closes` or lands near an existing record; then it waits in the tray. The bounce-and-exits protocol belonged to the v1 `save` tool and is retired. See [Delegation tiers](#/principle/delegation-tiers).

The global rules also require that a record id never appears bare in a reply. The owner cannot see what sits under an id, so every mention carries a one-line paraphrase. This site follows the rule. Principle articles give the reason, never the id.

## Reflection

`reflect` mines session transcripts for learnings that generalize and routes each to an edit on a skill that already exists. It has no new place of truth. Two read-only reviewers read the raw transcripts, and the synthesis happens in main.
