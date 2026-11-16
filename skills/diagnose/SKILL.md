---
name: diagnose
description: Disciplined diagnosis loop for hard bugs and performance regressions. Reproduce → minimise → hypothesise → instrument → fix → regression-test. Use when user says "diagnose this", reports a bug, or describes a performance regression.
---

> Provenance: derived from Matt Pocock's `skills/engineering/diagnosing-bugs/SKILL.md` (https://github.com/mattpocock/skills, MIT License, Copyright (c) 2026 Matt Pocock), edited by the repo owner. See THIRD_PARTY_NOTICES.md.

# Diagnose

Six phases. Skip one only with explicit justification. Hypothesise and reflect in LANGUAGE.md vocab.

## Input

- **Symptom string** — `/diagnose "Reverb broadcast not arriving on the order screen"`. Skip the Phase 1 probe.
- **No args** — Phase 1 probes the user for failure mode, repro steps, last-known-good. Don't guess.

## When to use

Non-trivial bugs: resists first guess, unclear failure mode, intermittent trigger, perf regression. For typos or obvious nil-derefs, just fix.

## Process

### 0. Load context (on demand)

Per `~/.claude/CONTEXT-LOAD.md`.

### 1. Feedback loop

**The whole skill.** With a fast deterministic pass/fail signal, you'll find the cause. Without one, no staring will save you.

If no symptom given, probe: failure mode, repro steps, last-known-good (commit/deploy/dataset/time window).

#### Ways to construct a loop (try roughly in order)

1. Failing test at whatever seam reaches the bug.
2. Curl/HTTP script against dev server.
3. CLI invocation with fixture input, diff stdout against snapshot.
4. Headless browser via Playwright MCP — `browser_navigate`, `browser_click`, `browser_type`, `browser_take_screenshot`, `browser_console_messages`, `browser_network_requests`. Canonical loop for UI/frontend bugs.
5. Replay captured trace (HAR, payload, event log).
6. Throwaway harness — minimal subset exercising the bug path.
7. Property/fuzz loop for "sometimes wrong output".
8. Bisection harness — `git bisect run` against an automated check.
9. Differential — old vs new (or two configs), diff outputs.

#### Iterate on the loop

Faster (cache setup, narrow scope). Sharper (assert the symptom, not "didn't crash"). More deterministic (pin time, seed RNG, isolate fs, freeze network).

A 2-second deterministic loop is a superpower. A 30-second flaky one is barely a loop.

#### Non-deterministic bugs

Goal isn't a clean repro — it's a **higher repro rate**. Loop 100×, parallelise, stress, narrow timing, inject sleeps. Raise until debuggable.

#### When you genuinely can't build a loop

Stop. State what you tried. Ask for: environment access, captured artifact (screenshot, HAR, log dump, core dump, screen recording), or permission for temporary prod instrumentation. **Don't hypothesise without a loop.**

### 2. Reproduce

Run the loop. Confirm:

- Failure matches what the **user** described.
- Reproducible across runs (or high enough rate).
- Exact symptom captured for later verification.

### 3. Hypothesise

3–5 ranked hypotheses before testing any.

≥2 hypotheses must name the architectural shape in LANGUAGE.md vocab — e.g. *"Leaky seam between Assistant module and Ollama adapter — adapter swallows transport errors, returns empty string, module treats as valid."*

Each must be **falsifiable**: "If <X>, then <changing Y> kills the bug / <changing Z> worsens it." Can't state the prediction → discard or sharpen.

Show the ranked list to the user. Don't block — proceed if AFK.

### 4. Instrument

One variable at a time. Each probe maps to one prediction.

1. Debugger/REPL if env supports it. One breakpoint beats ten logs.
2. Targeted logs at distinguishing seams.
3. Never "log everything and grep".

Tag every probe `[DEBUG-<id>]`. Cleanup becomes one grep.

**Perf branch:** baseline first (timing harness, `performance.now()`, profiler, query plan), then bisect. Measure, fix.

**UI branch:** drive the page via Playwright MCP. `browser_console_messages` + `browser_network_requests` are your distinguishing-seam logs; `browser_take_screenshot` captures state at each probe. Tag DOM-injected probes `[DEBUG-<id>]` like server logs.

### 5. Fix + regression test

Test before fix — but only if a **correct seam** exists. A correct seam exercises the real bug pattern as it occurs at the call site, not a shallower proxy.

**No correct seam → that's the finding** — note it; usually triggers `/improve-codebase-architecture`.

If a correct seam exists:

1. Failing test at that seam.
2. Watch it fail.
3. Apply fix.
4. Watch it pass.
5. Re-run Phase 1 loop against the original scenario.

### 6. Cleanup + post-mortem

Before declaring done:

- [ ] Original repro no longer reproduces.
- [ ] Regression test passes (or absence-of-seam is documented).
- [ ] All `[DEBUG-...]` removed (one grep).
- [ ] Throwaway prototypes deleted.
- [ ] Winning hypothesis stated in commit/PR.

Then emit the post-mortem and handoffs.

## Output

````
```diagnose-post-mortem
Bug: <one line — what the user observed>
Root-cause: <one line — what was wrong, LANGUAGE.md vocab when it fits>
Fix: <one line + path:line>
Regression: <test name + path, OR "no correct seam — see reflection">
Cleanup: <probes removed, prototypes deleted, follow-ups noted>

Reflection: <one paragraph — what made this hard, the seam's shape (module / interface / seam / adapter / depth / leverage / locality), what to remember>
```
````

Fill every field. `n/a` + one phrase if not applicable.

## Handoffs

- **`Recommend: /improve-codebase-architecture <scope>`** — root cause is **architectural** (class-of-bug, not a point fix). Signals: shallow module the fix couldn't deepen, missing seam forcing a hack, leaky adapter, same wrong assumption duplicated across N callers. Skip for typos, off-by-ones, wrong constants.
- **`Recommend: /review-structure`** — fix is non-trivial: ≥3 files OR crossed a module boundary (edits on both sides of a seam). Skip for single-file point fixes.

Neither fires → silence.
