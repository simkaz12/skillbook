<!-- Provenance: derived from Matt Pocock's `skills/engineering/domain-modeling/ADR-FORMAT.md` (https://github.com/mattpocock/skills, MIT License). See THIRD_PARTY_NOTICES.md. -->

# ADR format

ADRs live in `docs/adr/` with sequential numbering: `0001-slug.md`, `0002-slug.md`. Create the directory lazily — only when the first ADR is needed.

Every ADR is also mirrored to Tabularium (`memory_propose(kind="decision", headline, claim, rejected, audience?)`; the tile waits for the owner's approval) so it's searchable across sessions once approved. The file is the reviewable in-repo copy; the Tabularium record is the searchable mirror.

## Template

```md
# {Short title of the decision}

{1-3 sentences: the context, what was decided, and why.}
```

That's it. An ADR can be a single paragraph. The value is recording *that* a decision was made and *why* — not filling out sections.

## Optional sections

Include only when they add genuine value; most ADRs won't need them.

- **Status** frontmatter (`proposed | accepted | deprecated | superseded by ADR-NNNN`) — useful when decisions get revisited
- **Considered Options** — only when the rejected alternatives are worth remembering
- **Consequences** — only when non-obvious downstream effects need calling out

## Numbering

Scan `docs/adr/` for the highest existing number and increment by one.

## When to offer an ADR

All three must be true:

1. **Hard to reverse** — the cost of changing your mind later is meaningful.
2. **Surprising without context** — a future reader will look at the code and wonder "why on earth did they do it this way?"
3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons.

If a decision is easy to reverse, skip it — you'll just reverse it. If it's not surprising, nobody will wonder why. If there was no real alternative, there's nothing to record. Decisions that fail this test still go to Tabularium; they just don't get a file.

### What qualifies

- **Architectural shape.** The load-bearing structural rule a reader must not violate — e.g. "business logic lives only in one layer; the interface delegates and never computes," or "one swappable seam owns all vector-store access."
- **Deliberate deviations from the obvious path.** A place the code does something surprising on purpose — e.g. an update endpoint *silently drops* a field because that state changes through a dedicated path instead. A reader would otherwise "fix" the silent drop.
- **Boundary / scope decisions.** What's deliberately in and out — the explicit no-s matter as much as the yes-s.
- **Technology / infra choices with lock-in.** The store, the search engine, the provider layer, a runtime constraint — the ones that would take a quarter to swap.
- **Constraints not visible in the code.** A partner API contract, a compliance requirement, a business rule reversed in chat — anything a future reader can't infer from the source.
- **Rejected alternatives when the rejection is non-obvious.** Picked one approach over a plausible other for subtle reasons — record it, or someone re-proposes the loser in six months.
