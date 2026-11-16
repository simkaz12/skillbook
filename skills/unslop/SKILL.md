---
name: unslop
description: Strip AI tells from a piece of prose and put a human voice back in — an editing pass over existing text, not a generator. Use when the user says "unslop", "this reads like AI", "de-AI this", "humanize this", or hands over any finished text (doc, README, PR text, email, reply draft) to be reworked so it stops sounding generated.
---

> Provenance: derived from `pstack/skills/unslop` in https://github.com/cursor/plugins/tree/main/pstack (MIT License, Copyright (c) 2026 Lauren Tan); the owner added rules, a jargon list and exemptions. See THIRD_PARTY_NOTICES.md.

# Unslop

The global rules already apply this list to everything written here as it is written; this skill is the deliberate pass — take a finished text and work it over.

## Process

1. Scan for the patterns below.
2. Rewrite. Preserve meaning, match intended tone.
3. Add soul (next section).
4. Self-audit: "What still marks this as obviously AI-generated?" Fix what is left.

## Adding soul

Removing patterns is half the job. Sterile, voiceless writing is just as obvious.

- **Have opinions.** React to facts instead of neutrally listing pros and cons.
- **Vary rhythm.** Short sentences. Then longer ones that take their time. Mix it up.
- **Acknowledge complexity.** "Impressive but also kind of unsettling" beats "impressive."
- **Use "I" when it fits.** First person isn't unprofessional.
- **Let some mess in.** Perfect structure looks machine-made.
- **Be specific.** Not "this is concerning" but "there's something unsettling about agents churning away at 3am."

## Patterns to detect and fix

### Content

1. **Puffery.** "pivotal moment", "testament to", "evolving landscape", "setting the stage for", "indelible mark", "deeply rooted". Cut it, state what happened.
2. **Name-dropping.** Listing outlets or tools without context. Pick one, say what it said.
3. **Superficial -ing tails.** "highlighting…", "ensuring…", "reflecting…", "showcasing…", "fostering…". Delete, or expand into the real claim.
4. **Promotional adjectives.** "seamless", "powerful", "robust", "blazing-fast", "groundbreaking", "renowned", "nestled", "breathtaking", "stunning", "must-visit". Describe neutrally.
5. **Vague attribution.** "Experts believe", "industry reports suggest", "some critics argue". Name the source or cut.
6. **Formulaic challenge arcs.** "Despite challenges… continues to thrive." Give the specific facts.

### Language

7. **AI vocabulary.** Additionally, crucial, delve, enduring, enhance, fostering, garner, interplay, intricate, landscape (abstract), pivotal, showcase, tapestry, testament, underscore, vibrant. Replace with plain words.
8. **Fancy ways to say "is".** "serves as", "stands as", "boasts", "features". Say is or has.
9. **"Not just X, but Y."** State the point directly.
10. **Rule of three.** Forcing ideas into groups of three. Use the natural number.
11. **Synonym cycling.** Protagonist, main character, central figure, hero all in one paragraph. Pick one term and repeat it.
12. **False ranges.** "from X to Y" where the two are not on a shared scale. List the items.

### Style

13. **Em-dash monotony.** The character is fine. The tell is the same interrupt-and-restate construction three or more times in one paragraph. Vary or cut the third.
14. **Colon as a mid-sentence connector.** Fine before a list or an example. "If you're coming from traditional automation: instead of registering event handlers, you describe conditions" adds nothing with the colon — rewrite so the point stands without comparison framing.
15. **Boldface overuse.** Don't bold every proper noun or acronym.
16. **Inline-header lists.** The tell is a bold label and colon that restates the line: "**Performance:** Performance improved…". Convert to prose. A bold lead-in that ends in a period, names the item, and is followed by genuinely new detail ("**Schema in TypeScript.** Tables live in one file.") is fine.
17. **Title Case headings.** Use sentence case.
18. **Decorative emoji.** Remove from headings and bullets.
19. **Curly quotes.** Replace with straight quotes.

### Communication artifacts

20. **Chatbot phrases.** "I hope this helps!", "Let me know if…", "Of course!", "Certainly!", "Found the smoking gun!" Remove.
21. **Cutoff disclaimers.** "While specific details are limited…" Find the source or cut the sentence.
22. **Sycophancy.** "Great question! You're absolutely right!" Answer directly.

### Filler

23. **Filler phrases.** "In order to" → "to". "Due to the fact that" → "because". "It is important to note that" → delete.
24. **Stacked hedges.** "could potentially possibly be argued that it might" → "may".
25. **Generic conclusions.** "The future looks bright." State the plan or the fact.

### Jargon

26. **Abstract metaphor nouns.** Substrate, wedge, vector, locus, vantage, nexus, bedrock, modality, paradigm, gold-plating, ratchet, evacuate (of code), endgame, north star, flywheel. These read as technical but have a plainer concrete word. "Substrate" → "base". "Wedge in" → "add". "Vector" → "way". "Gold-plating" → "more than the job needs". "Ratchet" → the mechanism's real name, or "a limit that only tightens". "Evacuate" → "move out". "Endgame" → "the last phase". Pick the concrete word.

### Plain speech

27. **Say what it does, not how it feels.** "the database stays close at hand", "SQL you can read", "types that follow your schema" name a feeling. The fix names the mechanism or a number: "`.toSQL()` returns the exact string sent to the database", "a column rename fails the build". Ask what the sentence tells the reader to do or know, then write that. If you can't restate it as a concrete instruction, fact, or number, cut it. One more check: if the sentence could appear unchanged in another project's docs, it says nothing about this one. Cut it.
28. **Dense sentences.** One idea per sentence. If the reader backtracks to parse it, split it.
29. **Passive voice.** Name the actor. "queries are validated" → "the compiler validates queries", "the file is parsed by the loader" → "the loader parses the file". Passive only when the actor is unknown or genuinely doesn't matter.
30. **Adverbs propping up weak verbs.** "runs quickly" → "is fast" or the number. "significantly improves" → the measured delta. An adverb propping up a weak verb means the verb is wrong.
31. **Prefer the plain word.** "utilize" → "use", "leverage" (verb) → "use", "facilitate" → "help", "numerous" → "many", "in the event that" → "if". The fancier synonym is rarely clearer.
