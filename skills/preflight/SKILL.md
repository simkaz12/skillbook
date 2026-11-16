---
name: preflight
description: Pre-handoff gate that drives the running app against the four discipline slips a green unit/feature suite hides. Use right before handing work off for review, when the owner says "preflight" or "check before I push", or asks to map or refresh a repo's verification recipes; it exercises the real app, never re-runs the test suite as proof, and treats a passing suite as a precondition. For ticket work that has a brief, use verify-ticket instead.
---

# Preflight

`preflight` stays available to build or refresh a generic verification map and to run its four checks; it does not call `verify-ticket`.

## Precondition
Start from the latest base: run `bash ~/.claude/skills/../scripts/pull-base.sh --no-switch` in the repo first (and in its partner when the ticket spans both). Focused tests over the changed paths (the `focused:` commands in `$HOME/.claude/skills/../agent-projects/<scope>/testing.md`) and the linter already green. If not, run them first — preflight never runs the full suite, never substitutes for these checks, and never accepts green as proof.

## Mode
`.claude/features/` missing or empty → **build the map**, then gate. Map present → **gate**.

`.claude/PW_CREDS.md` is the repo's launch/doctor/auth authority and already exists in most repos. Extend it in place; never mint a second one.

## Who drives
Main runs this skill and owns the verdict. Browser work goes to a dispatched `hand-ex` whose dispatch prompt names the exact paths `.claude/PW_CREDS.md` and `.claude/features/<feature>.md`. It reads them as files, so it needs no skill it cannot load. Main writes the map files.

One driver at a time, and the contention is wider than the browser: a builder editing a component hot-reloads the page a live checker is mid-flow on. Any fan-out is a wave — builders in parallel while the browser idles, then browser work strictly single-file with no builders live.

## Build the map
Interview the repo, not the owner. Answer from the codebase and ask only what you cannot observe: what surface a user actually touches, how the app starts locally, how an agent drives it programmatically (an existing harness before a generic recipe), what evidence you can capture, whether two instances can run side by side.

`.claude/PW_CREDS.md` — keep what's there, fill what's missing:
- **Launch** — containers, ports, dev command, readiness check, teardown. Kill what you started, never by process name; teardown takes the instance, never the evidence.
- **Doctor** — one read-only check answering "is this instance worth driving?". It must assert *which* user is authenticated, not just HTTP 200 — a stale Sanctum cookie has silently authenticated a session as a previous user. Read identity (`fetch('/auth/user')` or the repo's equivalent) and compare against the id you intended.
- **Auth** — mechanism, a known-good user, and the permission caveat that makes them the right one.
- **Gotchas** — traps that waste or invalidate a run.

`.claude/features/<feature>.md` — one file per user-facing feature (top 3-5, from routes, menus, commands, docs) plus `README.md` indexing them. Exactly four H2s, in order:
1. `Sub-features` — short ids, one line each.
2. `How to get to it (user POV)` — every entry point.
3. `Driving it with <harness>` — opens with `Preconditions:`, then labelled bullets pairing each user action with the exact command and the observable end state. Stable handles (ARIA name, data attribute, route path) over coordinates and tab order.
4. `Gotchas`.

Keep implementation detail out: user paths, stable handles, required state, commands, observable proof.

**Prove it before handing it over.** Run the map's own instructions end to end once: launch, doctor, drive ONE mapped feature, capture evidence, clean up. Then confirm the evidence still exists at its named location. A map that was never driven is a draft, not a deliverable.

## Where it does not apply
A repo with no drivable surface gets a doctor and an honest refusal, not a map. A React Native app with no Detox or Maestro, where the only drivable surface is `expo start --web` (not the shipped surface), is the typical case. Write the Metro doctor and an explicit "not drivable from here" — never a feature map describing a harness that cannot reach the app.

## Gate
Drive the actual UI/endpoint through the map. Re-running unit/feature tests does **not** count as exercising a path here — that's the trap. For a BE-only change with no UI, hit the real HTTP endpoint instead — still never the test runner.

Doctor before the first drive and again after any failed drive. Where doctor can't see the failure — a wedged UI on a healthy process — reset to a known state or relaunch rather than hoping.

Each → PASS / FAIL / N-A, one line of evidence from the app.
1. **Happy path runs** — drive the main path the change adds, once. No crash / 500 / blank screen / console error.
2. **Requirement actually met** — for each spec/AC line, point to where the *running app* now does it. Nothing left "implemented in code, never seen."
3. **Bad input handled** — push one null/empty/invalid input through the path. Clean rejection, and any half-written record rolled back.
4. **Neighbour still works** — drive the pre-existing behaviour beside the change, not just the new thing. Confirm you didn't break what was there.

A drive that used one convenient entry point is incomplete when the feature file lists others.

## Output
```
## Preflight — <branch>  (<base>...HEAD, N files)
1 happy path    PASS  <what you drove, what you saw>
2 requirements  FAIL  "<criterion>" — not observable in app
3 bad input     PASS  <evidence>
4 neighbour     N-A   nothing pre-existing touched
verdict: NOT READY — <shortest path to green>
```
READY only if all four are PASS/N-A.

## Drift
A behaviour the map describes that the app no longer does is either doc drift (fix the map) or a product regression (report it, don't paper over it in the docs). Corrections land in `.claude/PW_CREDS.md` and `.claude/features/` only — never edit product code to make the map true.

## Guardrails
- When verification fails, suspect the observation method before suspecting the system. An a11y-tree click passes on a CSS-clipped dropdown; `.fill()` simulates paste rather than typing; a benchmark built through a fixture path that production never uses measures nothing; a delivered screenshot can conceal the true default render.
- Never push, create a PR, or hand off — preflight ends at the verdict; the owner ships.
