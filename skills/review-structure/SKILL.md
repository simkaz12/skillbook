---
name: review-structure
description: >-
  Explorer (not gate) for structural review of a diff, branch, or PR. Surfaces
  Strong / Worth-flagging / Worth-noting findings against 7 cursor-derived
  concerns, named in mattpocock vocab (module, interface, depth, seam, adapter,
  leverage, locality). Two-channel output — HTML for Strong + Worth-flagging,
  inline fenced block for nits. Triggers: review, code review, review my diff,
  audit, check-diff.
allowed-tools: Read, Bash, Grep, Glob, mcp__tabularium-mcp__recall, mcp__tabularium-mcp__decisions_query
disable-model-invocation: true
---

> Provenance: the seven concerns come from the `principle-*` skills in https://github.com/cursor/plugins/tree/main/pstack (MIT License, Copyright (c) 2026 Lauren Tan), named in Matt Pocock's vocabulary (MIT); the text is the repo owner's. See THIRD_PARTY_NOTICES.md.

# Review

No file edits, no formatters, no test runs.

Skip for one-liners. Reach for multi-file diffs, pre-merge branches, PRs.

## Input modes

| Invocation | Resolution |
|---|---|
| `/review-structure` (dirty tree) | `git diff HEAD` |
| `/review-structure` (clean tree) | `git diff HEAD~1..HEAD`; if no commits since upstream, ask |
| `/review-structure pr <token>` or `/review-structure pr for branch <token>` | Search PRs by token, diff the match |
| `/review-structure branch <token>` or `/review-structure <branch-keyword>` | Search branches for token, diff against merge-base |
| `/review-structure <digits>` | Try branch search first; fall through to PR# |

**Token extraction.** Drop fillers (`pr`, `for`, `the`, `branch`). Keep the meaningful keyword — digits, JIRA-id, slug fragment.

**Branch resolution.** `git for-each-ref --format='%(refname:short)' refs/heads refs/remotes | grep -i <token>` → single match → `git diff $(git merge-base <branch> HEAD)..<branch>`. 0 matches → `git fetch`, retry. >1 → list candidates, ask.

**PR resolution.** `gh pr list --search "<token>" --json number,title,headRefName` → single match → `gh pr diff <#>`. 0 → say so. >1 → list `(#num — title — branch)`, ask.

## Process

### 1. Load context (on demand)

Per `~/.claude/CONTEXT-LOAD.md`.

### 2. Resolve diff scope

Apply input-mode table. Capture changed files, diff text, base/head refs.

### 3. Walk against the 7 concerns

Walk hunks against each concern below. Don't deduplicate — repeated firings are signal. Skip style covered by Pint/ESLint.

Opportunistic recall:
- Prior decisions → `mcp__tabularium-mcp__decisions_query(query=<topic>, scope=<scope>)`.
- Blast radius → `Grep` the symbol across the repo for callers outside the touched file.

### 4. Classify

- **Strong** — unmistakable structural mistake, costly to undo.
- **Worth-flagging** — plausible, reasonable people might disagree.
- **Worth-noting** — nit, no architectural weight.

When torn between Strong and Worth-flagging, prefer Worth-flagging.

### 5. Render HTML

Strong + Worth-flagging → render as one self-contained HTML report (same card shape as improve-codebase-architecture).

- `<skill>` = `review-structure`
- TITLE = `Review: <project> — <scope>`
- FINDINGS = one `<article class="finding severity-strong|severity-worth-flagging">` per finding; add `<pre class="mermaid">` for shape-arguments.

Zero Strong + Worth-flagging → skip HTML, print: `No Strong or Worth-flagging concerns; <N> nits below.`

### 6. Inline nit block

````
```review-nits
path/to/file.ext:42 — short description
```
````

One nit per line, no cap. Omit block if zero.

### 7. Handoff

Emit `Recommend: /improve-codebase-architecture <subsystem>` if a Worth-flagging concern is **subsystem-scoped** — shape problem lives in code beyond the diff and the diff is too narrow to host the fix. Local-to-diff concerns don't trigger. Silence otherwise.

Emit the line; don't invoke `/improve-codebase-architecture`.

## The 7 concerns

Walk in order. Overlap fires both.

### 1. Useless code

Deletion test: *if I delete this, what breaks?* Flag dead code, pass-through modules, speculative parameters/flags, comments restating code.

Pass-through deletions → Worth-flagging (often subsystem-scoped). In-diff dead code → Worth-noting.

### 2. Duplication

Shared *meaning*, not shared syntax. Flag repeated constants, validation in two places, parallel branches across N call sites, copy-paste across new files.

Multi-subsystem duplication → Worth-flagging. In-diff copy-paste → Worth-noting.

### 3. Wrong abstraction

Interface forces callers to know things they shouldn't, or hides things they need. Symptom: callers fight the abstraction (options-bag hacking, `if mode === 'foo'` branching, casting).

Flag interfaces exposing implementation detail, interfaces hiding essential context, premature DSLs, and **diffs contradicting decision memory** (Strong if the decision is in force, Worth-flagging if superseded).

### 4. Misplaced seams

**One adapter = hypothetical seam; two = real.** Don't introduce a seam unless something varies across it.

Flag single-adapter seams with no test fake, seams cut mid-logical-unit, 1:1 wrappers, seams whose two adapters need callers to know which they have.

New hypothetical seam → Worth-flagging. Misplaced seam in hot path → Strong.

### 5. Boundary noise

Information crossing a module's interface that only one side needs. Each extra item is leverage lost.

Flag pass-through parameters, return types with unused fields, side effects callers work around, options-bags where 80% use the default.

Subsystem-wide widening → Worth-flagging. Single noisy parameter → Worth-noting.

### 6. Shallow module

Symptoms: thin method wrappers, getX/setX mirroring private state, "manager"/"helper" aggregators, fat constructor + tiny method tails.

New shallow module → Worth-flagging. Shallow tail on existing module → Worth-noting.

### 7. Test seam shape

Tests cross the same seam as callers.

Flag heavy mocking of direct collaborators, reflection on private state, missing tests when a correct seam exists (Worth-noting), missing tests when no correct seam exists (Worth-flagging finding in itself), and **layered tests after a deepening** — replace, don't layer; delete absorbed unit tests.

