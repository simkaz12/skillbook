---
title: Flow of work
covers: skill/flow, skill/recon, skill/grill-me, skill/grill-with-docs, skill/to-spec, skill/wayfinder, skill/improve-codebase-architecture, skill/diagnose, skill/land, skill/what
---

A piece of work passes through up to five stages, and each stage has a skill. Nothing requires every piece to use all five. The point is that the stage a piece skips is a choice, not an accident.

## The path

1. Investigate. `recon` is a reconnaissance pass that gathers the context the next decision needs, read-only, starting narrow and widening only when a named gap needs it. Most of its use is on work tickets, so its entry point takes one. `diagnose` does the same for a hard bug, with a loop from reproduction to regression test.
2. Agree. `grill-me` questions the owner until requirements and design choices have a shared shape. `grill-with-docs` does the same and also writes the glossary and the hard calls into the repository.
3. Brief. `to-spec` turns the settled agreement into an execution brief with scopes, verify steps and an out-of-scope line. A brief can be solo or split into independent lanes. Work too large for one session goes to `wayfinder`, which maps it as decision tickets.
4. Execute and review. `spec-runner` runs the brief and `spec-reviewer` gates the result. [Review gates](#/principle/review-gates) covers that half.
5. Land. `land` commits, pushes and opens the pull request in the repository's own convention, and only after a current `verify-ticket` proof.

A quick fix is an owner-triggered exception outside the stages: main edits, one hand verifies, nothing lands.

`flow` sits above the five. It keeps one piece of work in one active thread, picks the smallest next step that removes a named uncertainty and carries the agreement across handoffs. It does not replace the skills it routes to. Calling `recon` or `to-spec` directly still works.

`improve-codebase-architecture` is outside the path on purpose. It finds deepening opportunities in a scoped subsystem and proposes refactors, and it is the only skill with its own grilling built in. `what` is a seven-line escape hatch for the moment a message did not land.

## Why it is shaped like this

Repeated discovery is the cost these skills are built around. `flow` names it in its own description, and the brief answers it by writing the behaviour, the decisions, the constraints and the evidence down once, with a `to-spec` rule that the runner and reviewer receive the brief and the evidence it links. The runner and reviewer start in fresh windows and judge from the same agreement.

The earlier machinery was cut for cost. A kanban loop (a PRD skill, an issue splitter and a driver) was dropped in August 2026 after the owner asked for a clean slate. The gauntlet, one builder plus two critics for up to three rounds, was dropped in September after two runs showed the critic rounds cost far more than they caught. What replaced it is the split brief, with parallel runner lanes and one Codex gate in the review after integration.
