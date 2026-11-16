---
name: grill-with-docs
description: >-
  Grilling session that stress-tests a plan against the project's existing
  domain model, sharpens terminology, and writes the result down as it
  crystallises. Use when the user wants to grill a plan AND capture the
  domain model durably; grilling without capture is grill-me. Triggers:
  "grill with docs", "grill and document", stress-test against our
  language, build/update the glossary.
---

> Provenance: derived from Matt Pocock's `skills/engineering/grill-with-docs/SKILL.md` (https://github.com/mattpocock/skills, MIT License, Copyright (c) 2026 Matt Pocock), edited by the repo owner. See THIRD_PARTY_NOTICES.md.

The interview loop runs as in `grill-me`; this skill adds the capture behaviour.

This is the durable-capture variant of `grill-me`. `grill-me` leaves nothing behind; this skill writes glossary terms, ADRs, and Tabularium decisions inline *as they resolve*. Use the architecture vocabulary in `~/.claude/LANGUAGE.md` (module / interface / seam / depth) when discussing structure — that file is generic and separate from the project glossary you build here.

## Locate the docs

By default a repo is single-context: one `CONTEXT.md` at the repo root, ADRs in `docs/adr/`. If neither exists yet, create each lazily — only when you have the first real thing to write.

If a `CONTEXT-MAP.md` ever appears at the root, the repo has split into multiple contexts; read it to find which `CONTEXT.md` the current topic belongs to. Format details: [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md).

## During the session

**Challenge against the glossary.** When a term conflicts with an existing `CONTEXT.md` definition, call it out at once: "Your glossary defines 'prospect' as X, but you seem to mean Y — which is it?"

**Sharpen fuzzy language.** When a term is vague or overloaded, propose a precise canonical one. "You're saying 'account' — Sales Account or the user's login? Those are different things."

**Discuss concrete scenarios.** Stress-test domain relationships with invented edge-case scenarios that force precision about boundaries between concepts.

**Cross-reference the code.** When I claim how something works, check whether the code agrees before accepting it. Navigate by the project's own conventions — its `CLAUDE.md` documents the code map / layout — plus Glob and grep. Surface contradictions: "Your code retires the whole record, but you just said a partial retire is possible — which is right?"

**Update CONTEXT.md inline.** The moment a term resolves, write it — don't batch. `CONTEXT.md` is a glossary and nothing else: no implementation details, no spec, no scratch pad. Format: [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md).

## Recording decisions

Two tiers — most decisions are tier 1.

1. **Tabularium (always).** Any non-obvious decision goes to Tabularium via `memory_propose(kind="decision", headline, claim, rejected, audience?)`. State the decision in `claim` and the alternative ruled out in `rejected`. The reason is the thread excerpt the tile carries. If you cannot name what was rejected, propose it as a `fact` instead. The tile waits for the owner's approval, and the authoritative cross-session record exists once the owner approves it.

2. **ADR (sparingly) + Tabularium.** Only when all three hold: hard to reverse, surprising without context, and the result of a real trade-off. Then also write `docs/adr/NNNN-slug.md`. Format and the three-part test: [ADR-FORMAT.md](./ADR-FORMAT.md).

If a decision fails the ADR test, skip the file — the Tabularium record is enough.

## Handoff

The conversation history plus the artifacts you wrote (CONTEXT.md, ADRs, Tabularium decisions) are the asset. When I signal alignment is reached, proceed to `to-spec` in this session — it leans on the glossary and ADRs you just captured. Do not force a digest, clear context, or fresh main session.
