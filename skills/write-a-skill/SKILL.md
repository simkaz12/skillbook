---
name: write-a-skill
description: Author or revise a Claude skill as a deep module — a tight description plus a lean SKILL.md over detail that loads on demand. Use when creating, writing, or rewriting a skill, critiquing one, or when a skill is bloated, generic, never triggers, or fires when it shouldn't.
disable-model-invocation: true
---

> Provenance: the name and concept follow Matt Pocock's skills (https://github.com/mattpocock/skills, MIT License); the text here is the repo owner's own rewrite. See THIRD_PARTY_NOTICES.md.

# Write a skill

A skill is a module. Its **interface** is the `description` (the only thing read at discovery time) plus the SKILL.md body (read once loaded); its **implementation** is everything behind that — sibling files, scripts, examples. Good skills are **deep**: a lot of behaviour behind a small interface. Apply the same discipline you'd apply to any module — the vocab lives in `~/.claude/LANGUAGE.md`; read it first.

## First, the deletion test

Before writing anything, ask: if this skill didn't exist, what breaks?

- If the model would already do the task well from general knowledge, a skill is shallow indirection — **don't write it.**
- A skill earns its keep only when it encodes something the model wouldn't otherwise do: a project-specific procedure, a hard-won sequence, a non-obvious convention, a deterministic script, or a handoff between other skills.

## The description is the interface

It is the only thing the agent reads when deciding whether to load the skill — the discovery seam, and the test surface. If it triggers wrongly or never triggers, the description is wrong, not the body.

- Third person, ≤1024 chars, two sentences.
- Sentence 1: what it does. Sentence 2: `Use when [concrete triggers]` — real phrases the user would say, contexts, file types.
- Make it deep: maximum trigger-coverage per word. Generic descriptions ("Helps with X") collide with every neighbour and never get picked. Name what makes this skill the right one over its siblings.
- Mind the budget: a model-invocable description sits in the system prompt of every session, so it's paid for whether or not the skill fires. Keep it to what it is plus when to use it — triggers, anti-triggers, sibling discriminators — and leave mechanism detail to the body. A skill marked `disable-model-invocation: true` is slash-only, never loaded into the system prompt, so its description pays no per-session cost and is exempt from the budget.

## Keep the SKILL.md lean

Progressive disclosure *is* depth applied to skills. The body is interface, not implementation — keep it tight, push detail one level deep into sibling files that load only when the task needs them.

- Target: the body fits on a screen or two. If it sprawls, the skill is shallow — split it.
- Sibling files (one level deep, relative-path links) hold long reference, format templates, examples, scripts.
- Don't duplicate what exists — reference `~/.claude/LANGUAGE.md` for vocab; point at a sibling skill rather than re-explaining its job.

## Compose at seams; don't own loops

Skills are modules with seams between them. A skill should do one thing and hand off, not swallow the whole workflow.

- Name the handoff explicitly ("after this, run `to-spec`"), the way `grill-me` → `to-spec` → `/review-structure` chains.
- Prefer a skill that ends and points to the next over one that drives a loop internally. The seam is what lets a skill be swapped or deleted without rewriting its neighbours.

## House style

- Terse. No filler, no restating what the model already knows, no motivational preamble. The unslop catalog in `~/.claude/CLAUDE.md` names the specific tells and applies here without being invoked.
- Zero comments in any bundled script.
- Ground examples in this toolkit's real skills, not invented PDF/finance scenarios.
- No time-sensitive info; consistent terminology; references one level deep.

## Build it

1. Apply the deletion test. If it survives, name the one job in a sentence.
2. Write the description first — it's the interface. Get it sharp before the body.
3. Draft a lean SKILL.md. Anything past a screen or two goes in a sibling file.
4. Add a script only for deterministic work (validation, formatting) that would otherwise be regenerated each run.
5. Self-check: would it trigger on the right phrases and nothing else? Delete any section — does the skill still work? If yes, it was padding.
