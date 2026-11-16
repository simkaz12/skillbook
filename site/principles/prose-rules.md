---
title: Prose rules
covers: skill/unslop, skill/write-a-skill, doc/LANGUAGE.md, doc/GLOBAL-CORE.md
---

Two sets of rules govern text here. One keeps prose from reading as generated. The other fixes the words used to talk about architecture.

## No slop, at write time and again after

The global rules apply a 31-pattern list to every artifact and every reply, from specs and recon reports to commit text and conversation. It names puffery, promotional adjectives, a list of tell-tale words, "not just X but Y", the rule of three, synonym cycling and a dozen more. After drafting, the writer asks what still marks the text as generated and fixes that.

`unslop` is the deliberate second pass. It takes a finished text and edits it, and it adds a voice back, because sterile text is just as obvious. The same list applies while writing, so the skill is a rework of finished text and not the only line of defence.

Default replies are terse. Full prose is for grilling, discovery and teaching. There are no inline code comments unless the owner asks for them, and the rule has no exception for comments that explain why.

Exact field names, commands and quoted output stay verbatim, and so does the architecture vocabulary below.

## Architecture vocabulary

[LANGUAGE.md](#/doc/LANGUAGE.md) fixes a small set of terms and bans their near synonyms. A module is anything with an interface and an implementation, at any scale. An interface is everything a caller must know, which includes ordering, error modes and configuration, not only the type signature. Depth is leverage at the interface. A seam is where an interface lives, and an adapter is whatever satisfies it. Locality is what maintainers get when change and bugs concentrate in one place.

The ban is deliberate. "Component" and "service" carry commitments to a test scope or a deployment shape. "API" drifts toward HTTP. "Boundary" blurs where the interface is. The words index the concepts and the concepts index each other, so a review that uses them loosely stops being comparable to the last one. `improve-codebase-architecture`, `review-structure` and `diagnose` load the file before they name anything.

## Writing a skill

`write-a-skill` applies the same depth idea to skills. A skill is a module, so its description is the small interface and its body is the implementation that loads on demand. A bloated or generic skill, or one that never triggers, is the shallow case.

