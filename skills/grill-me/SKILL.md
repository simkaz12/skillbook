---
name: grill-me
description: Align unresolved requirements, expectations, and design choices with the owner until the work has a shared shape. Use when the owner wants to stress-test a plan, get grilled on a design, mentions "grill me", or a fact-finding pass leaves non-derivable product decisions open.
---

> Provenance: the name and concept follow Matt Pocock's skills (https://github.com/mattpocock/skills, MIT License); the text here is the repo owner's own rewrite. See THIRD_PARTY_NOTICES.md.

Map the open questions as a tree. The frontier is every question whose prerequisites are settled. A call that follows directly from the evidence, an adopted standard, or a settled decision is a default, not a question: list each default in one line with its reason so the owner can veto it. Before asking, check each candidate against the ticket text, the tester's comment and the code; only what none of those answers is a question, the rest are defaults (owner, 2026-11-02: five questions asked, all five answerable from those sources). Ask only the questions whose answer changes the work, **at most 3–5 per round**, numbered `Q1..Qn`, each with a recommended answer marked `Recommended:`. The exception is a question only the reporter can settle, or one recon tagged `[product decision]`: it carries no `Recommended:`. Offer three closures instead: post it on the Jira ticket and hold the dependent scope; settle it with named comparative evidence, such as the sibling surfaces or the reporter's screenshot replayed; or waive it with the predicted bounce named ("ship reading A; if the reporter means B, it comes back"). "Go with your rec" does not close it. When more remain, ask first the ones later questions depend on, and name what the next rounds hold. After the owner replies, recompute the frontier and ask the next round. Explore questions answerable from the codebase instead of asking; dispatch facts needed from elsewhere to agents instead of asking. The grill ends when the frontier is empty.

Recon lists defects left in the touched area as fold-in candidates. Put each to the owner as fold in, leave, or close as no longer real, with a recommended default, inside the same rounds, and carry the answers into the agreement for `to-spec`.

When recon or a map already established facts, inherit those paths, revisions, and uncertainty labels. Spend the grill on expectations and choices they cannot settle; recheck only evidence that conflicts with the current surface or leaves a material gap.

The conversation history is the asset — do not produce a separate document. At alignment, state the compact agreement that `to-spec` needs: observable behavior and examples, locked decisions with rationale and rejected choices where relevant, constraints and out-of-scope, evidence paths and revisions, and any open question. An unresolved product decision blocks dependent implementation; do not silently choose it. Mark each unanswered default `default (not vetoed)` in the agreement; it stays binding.

Proceed to `to-spec` in this session.
