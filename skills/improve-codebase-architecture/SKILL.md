---
name: improve-codebase-architecture
description: Find deepening opportunities in a scoped subsystem and propose refactors. Use for "improve architecture", "deepen", "find refactor opportunities", "architecture review of <subsystem>".
disable-model-invocation: true
---

> Provenance: derived from Matt Pocock's `skills/engineering/improve-codebase-architecture/SKILL.md` (https://github.com/mattpocock/skills, MIT License, Copyright (c) 2026 Matt Pocock), edited by the repo owner. See THIRD_PARTY_NOTICES.md.

# Improve codebase architecture

## When to use

One scoped subsystem at a time — directory, module, or named system ("AI router", "broadcast pipeline"). Not whole-repo. Not ad-hoc diff review (that's `/review-structure`).

## Input

- `<path>` — a file or directory in the repo.
- `<subsystem-name>` — a named subsystem; resolve via the repo's code map + memory recall.

No args → ask.

## Process

### 1. Explore

1. Per `~/.claude/CONTEXT-LOAD.md`.
2. Subsystem drill: read the repo's code map (`CLAUDE.md`) and Glob/Grep the owning directories for subsystem gravity. Capture key symbol names.
3. Recall decisions for the scope — compose query from scope + symbols captured above:

   ```
   mcp__tabularium-mcp__decisions_query
     scope: <Tabularium scope>
     query: <scope name + key symbols>
     limit: 20
   ```

   In-force decisions are load-bearing; superseded or revoked ones are context only.
4. Walk the scoped code (`Read`, `Grep`, `Glob`). Broad scope → dispatch `hand-ex` explorers primed per the rules below. Apply the deletion test.

5. **Conflict check per candidate.** Compare against recalled in-force decisions. If a candidate contradicts one, **do not propose**. Build a *conflict card* instead:
   - decision id + verbatim text,
   - the contradicting candidate,
   - the friction that prompted it.

   Conflict cards tagged `severity-worth-flagging`.

### 2. HTML cards

Six fields per card:

1. **Files** — paths + line refs.
2. **Problem** — what's wrong, in LANGUAGE.md vocab. Reference decisions if relevant.
3. **Solution** — the deepened shape. Name new module, interface, seam, adapters.
4. **Benefits** — in terms of **leverage** + **locality** (and test-surface where it fits).
5. **Before-after diagram** — required. `<pre class="mermaid">` with `flowchart LR` (default) or `sequenceDiagram` (when ordering matters).
6. **Recommendation-strength** — **Strong** (deletion-test-positive, two adapters justified, clear locality win) or **Worth-flagging** (trade-off, single-adapter today, conflict card). No Worth-noting cards.

Render the cards as one self-contained HTML page and open it. Each card is one `<article>` with class `severity-strong` or `severity-worth-flagging`. Mermaid loads from a CDN script tag.

- `<skill>` = `improve-codebase-architecture`
- TITLE = `Improve: <project> — <scope>`
- FINDINGS = one card per `<article>`; only `severity-strong` and `severity-worth-flagging` classes apply.

Zero cards → skip HTML, print: `No deepening opportunities found in <scope>.`

After opening, ask which card to grill. Default: highest Recommendation-strength.

### 3. Grill topics

1. **Derive grill topics for the picked card.** A topic is a concrete unknown the card leaves implicit and the user can't resolve from the 6 fields. Candidates:

   - Module shape after deepening — what sits behind the new seam exactly?
   - Caller migration — what fights the new interface?
   - Test surface drift — which tests survive, which get rewritten?
   - Adjacent decisions — memory the card didn't conflict-check.
   - Single-adapter risk — if Recommendation = Strong on two-adapters-justified, is the second adapter real?
   - Locality cost — what gets harder if the deepening is wrong?

   Skip topics the card already answers.

2. Emit handoff. **Don't fire `/grill-me`**

   ```
   Recommend: /grill-me — for card "<title>":
   - <topic 1>
   - <topic n>
   ```

   Zero topics → no handoff.

## Subagent priming

Phase 1 step 4 subagent prompts must include:

- Project identifier.
- Scope.
- Recalled `kind=decision` entries verbatim.
- `~/.claude/LANGUAGE.md` (inlined or by absolute path).

The subagent starts with none of this context; without these four items it cannot check candidates against settled decisions.
