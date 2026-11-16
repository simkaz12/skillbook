---
name: to-spec
description: >-
  Turn a settled agreement into a solo or split execution brief without
  rediscovering its design; when decision territory is genuinely open, stop and
  tell the owner it needs `/wayfinder`. Use after grilling reaches alignment, or
  when the owner asks for an execution brief, split brief, or "to-spec".
---

> Provenance: the name and concept follow Matt Pocock's skills (https://github.com/mattpocock/skills, MIT License); the text here is the repo owner's own rewrite. See THIRD_PARTY_NOTICES.md.

# to-spec

`to-spec` packages agreement already reached in the live conversation, recon report, or wayfinder map. It formats and divides work; it does not re-interview or commission another design pass. If an inherited fact is uncertain or conflicts with the current revision, verify only that path. A non-derivable product decision remains open and blocks its dependent scope.

## Process

1. Read the agreement and its linked evidence. If a reset lost needed context, recover the existing recon report, map, or prior brief before Tabularium. Still missing a decision that affects behavior → hand off to `grill-me`, stop.
2. Pick the route: one scope, or scopes that all share the same files → solo brief; two or more scopes → split brief, always (owner ruling, 2026-10-13 and again 2026-10-29). A Blocks chain is not a reason for solo: it becomes a later wave. Solo for a multi-scope brief needs the owner's word for that brief, stated before dispatch. Open decision territory too large for the live work → stop and tell the owner it needs `/wayfinder`. Solo and split use the template below; split adds its dispatch plan.
3. Fill every scope in dependency order. A runtime claim that a locked decision depends on must be `[ran]` before the lock, for example one captured request. A decision that is not in the inherited agreement goes to the owner before dispatch. An `Uncertainty` line about the reporter's intent or a `[product decision]` dispatches only when it records one of grill-me's three closures: posted on Jira with the ticket held, settled by named comparative evidence, or an owner waiver naming the predicted bounce. Otherwise stop before dispatch. An Out of scope line that names something the tester sees on the next click (a control that no longer means anything, a list that will not show the new value) is not allowed. It becomes a scope, or a question posted on the Jira ticket before dispatch, with the ticket held until answered. Two scopes that send different payloads to the same endpoint for the same user intent must say why in the decision that splits them. An accepted fold-in defect becomes a scope only once its trigger is `[ran]` reachable: a query or request that builds the triggering state. A `[read]` trigger goes back to the owner as unproven. The scope names the defect id in **Build:**; once the brief is saved, call `memory_take {recordId}` for each one. A defect the owner closed as no longer real becomes a `memory_propose` with `closes` and the owner's words as the excerpt. Make `Verify` prove the stated behavior, not a generic green suite. A scope that conditionally renders a bound form field verifies a toggle away and back, then checks the submitted payload. For solo and split briefs, scope Verify contains focused checks. Schedule shared build and cross-scope checks once. Full-suite evidence belongs to `verify-ticket`'s daily baseline.
4. Save project work at `<repo>/docs/specs/YYYY-MM-DD-<slug>.md`; save global or cross-repo work at `~/.claude/specs/YYYY-MM-DD-<slug>.md`.
5. Dispatch execution only when the owner has already authorized implementation.

## Split route

Splitting keeps a runner's context small and buys wall clock. It does not save tokens; the owner wants it anyway for every multi-scope brief, so token cost is not a reason to go solo.

- For split briefs, add `## Integration verify`: build and cross-scope commands with expected output, never the full suite; the integrate-mode runner runs them once.
- Every scope has **Blocks:** (scope numbers that must land first, or `none`) and a scope-local **Verify:**: a named test or filter, or lint over the scope's files. Never put the full suite or app build there; the build and cross-scope checks belong to integration, and the full suite belongs to `verify-ticket`. A lane is an ordered list of scopes that share a file, or chain by Blocks with no other scope depending on either end. A scope whose Blocks span lanes gets its own later lane. Lanes within a wave have disjoint Files. Name any test in the filter that is red in the daily baseline as an expected failure. A Verify must run from the runner's own tree; a live check that depends on a component outside the diff goes under `## Integration verify` as an observation, not a scope gate.
- Add `## Dispatch plan`: merge scopes that share files or chain without other dependents. Later waves wait for named Blocks. A failed lane skips any lane that names one of its scopes. Example:

  ```
  Wave 1: lane A = scopes 1, 3 · lane B = scope 2
  Wave 2: lane C = scope 4 (blocks: 1, 2)
  Integrate: spec-runner mode: integrate
  ```

For a split brief, main dispatches each lane in a wave with `brief` and `scopes`. A lane lands only when every one of its scopes reports `done` or `needs-human`; one failed scope means its whole lane is unlanded. Dispatch a later lane only when every scope named in its **Blocks** belongs to a landed lane. Skip every lane that names a scope from a failed lane, not only the scope that failed. After the last wave, dispatch the integrator with `mode: integrate` and every scope number from landed lanes; it verifies only those scopes, reports unlanded work as `PARTIAL`, then runs integration checks. Codex runs once, in the `spec-reviewer` pass after integration; send it the integrator's verdict. A lane-only review runs no Codex (`gate: deferred`).

## Brief template

```md
# <Title>

## Problem / Solution
<user-visible problem and expected behavior>

## Inherited agreement
### Observable behavior and examples
<before/after examples and acceptance path>

### Evidence
- <claim> — <observed result, or explicitly untested assumption> — <path or runtime check> @ <revision if known> [ran|read|recalled]

### Uncertainty
- <open fact, or `none`> — <what would settle it>

## Decisions locked
- D1: <decision> — because <rationale>; rejected: <alternative, when relevant>

## Constraints
<compatibility, caller/type/module sketch only when it helps implementation, and other limits>

## Execution plan
Scope-ordered. Per scope:
- **Files:** exact paths (Create / Modify / Delete)
- **Blocks:** <scope numbers that must land first — split briefs only>
- **Build:** what this scope ships
- **Steps:** concrete edits, commands, values in order
- **Verify:** test / command + expected output / manual acceptance check

## Out of scope
<definition of done; nothing the tester meets on the next click>

## Review handoff
<runner and reviewer receive this brief plus only the linked evidence relevant to their scope. A failed result returns as local fix, missing fact, or decision reopening. A non-git surface states `task mode` and lists the paths Codex must review; the reviewer owns the command.>
```

Keep a small brief small: omit empty inherited-agreement subheadings, evidence, uncertainty, constraints, and rejected alternatives. Add caller usage, types, or a module sketch only when they stop an implementer from having to infer the shape.

