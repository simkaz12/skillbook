# Third-party notices

Most of this repository is original work by its owner. The items below are not, and are listed with their licenses. Where a file derives from someone else's work, a provenance line at the top of the file says so.

## Matt Pocock's skills (MIT)

Source: https://github.com/mattpocock/skills

Derived from upstream text and edited by the repo owner (provenance line at the top of each file):

- `skills/wayfinder/SKILL.md` (and `skills/wayfinder/agents/openai.yaml`, a small agent-metadata file shipped with it)
- `skills/what/SKILL.md`
- `skills/diagnose/SKILL.md`
- `skills/grill-with-docs/SKILL.md`, `skills/grill-with-docs/ADR-FORMAT.md`, `skills/grill-with-docs/CONTEXT-FORMAT.md`
- `skills/improve-codebase-architecture/SKILL.md`
- `LANGUAGE.md` (the architecture vocabulary and principles; the examples are the owner's)
- The short "vocab" section in `GLOBAL-CORE.md`, which summarizes `LANGUAGE.md`

Same skill names and concepts, text rewritten by the owner: `skills/grill-me`, `skills/to-spec`, `skills/write-a-skill`. `skills/review-structure` uses the vocabulary above but is not derived from an upstream skill.

The repo history here does not record which upstream commit each file started from, and upstream has since reorganized, so the derivation is stated from the file contents and names rather than a pinned revision. Treat these files as Matt Pocock's work as modified.

```
MIT License

Copyright (c) 2026 Matt Pocock

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## pstack by Lauren Tan (MIT)

Source: https://github.com/cursor/plugins/tree/main/pstack

- `skills/unslop/SKILL.md`: derived from `pstack/skills/unslop`, with rules, a jargon list and exemptions added by the owner.
- `skills/blast-radius/SKILL.md`: derived from `pstack/skills/blast-radius`, edited by the owner.
- `skills/reflect/`: the name and the idea of mining session transcripts come from `pstack/skills/reflect`; `judgment-reviewer.md` and `tooling-reviewer.md` are adapted from pstack's reviewer references, and the rest is the owner's rewrite.
- `skills/review-structure/SKILL.md`: the seven structural concerns come from pstack's `principle-*` skills; the text is the owner's.

```
MIT License

Copyright (c) 2026 Lauren Tan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## TypeSafe AI skill (MIT)

`skills/typesafe-ai/` is a vendor skill for TypeSafe AI's documentation and SDKs. It is kept as shipped, with its own `LICENSE` (Copyright (c) 2026 TypeSafe AI). It is not the owner's work.

## Vendored web assets

`site/vendor/marked.min.js` is marked v18.1.0 (MIT, MarkedJS and Christopher Jeffrey), unmodified; its license header is kept in the file. `site/vendor/fonts/` holds Bricolage Grotesque and Literata under the SIL Open Font License 1.1, with their license files next to the fonts.

## Third-party tools referenced but not included

Claude Code, Codex CLI (the `codex` plugin for Claude Code), Playwright MCP, T3 Code, Omarchy and the Tabularium memory server are used or called by this configuration. None of their code is included. Tabularium is the owner's own server and is not published here.
