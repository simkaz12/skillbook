# Global Rules

## Git

- **Never commit, branch, push, stash, reset, or check out over a dirty tree** unless the owner asks or the repo's CLAUDE.md grants it for a named case (arx: landed cards); the tree holds the owner's uncommitted work and a conflicting `stash pop` loses it. The owner handles all other git.
- **No rebases, ever.** Land stranded or unmerged work as plain uncommitted working-tree changes on the target branch (git apply of the original commit's diff), never by rebasing the old branch.
- **Start from the latest base** (owner ruling, 2026-10-23, PROJ-784). At thread start and in verify-ticket, preflight, recon, flow and land, run `bash ~/.claude/skills/../scripts/pull-base.sh --no-switch`. Exception (owner ruling, 2026-11-04): verify-ticket run inside flow skips it, since flow already pulled at its start. On the base branch it fast-forwards the checkout; elsewhere it fast-forwards only the local base ref and reports the gap, so committed work stays in HEAD. qa-ticket runs the plain form, which also moves a parked feature-branch checkout onto the base, where the code under test lives. Run it in the repo and in its partner from `Projects/CLAUDE.md` when the piece spans both. The session-start hook says when a repo is behind. Do not ask first. It fast-forwards only, backs the dirty tree up to a patch before any revert, reapplies the overlap, and never stashes, merges or rebases. Exit 3 or 4 means stop and report what it printed. This is the one sanctioned git write outside the rule above.

## Operating defaults

- **No inline comments** in code, ever, unless the owner asks. This includes "why" comments, and it covers edits to existing files as well as new ones: add no explanatory comments while touching surrounding code, and do not restore ones a previous pass removed. Existing comments in code you are not otherwise changing stay. Docblocks a framework or static-analysis gate requires are not inline comments.
- **Say what will change.** Before an action that changes production state (a deploy, migration, restart, bulk write), state the consequence in plain terms, such as which service restarts or how many rows get written, and let the owner react to that.
- **Concise-default rule.** Default to terse responses. Full prose only during grill-me / discovery / teaching contexts. `caveman` mode is the further-compressed escalation, not the default.
- **Memory access rule.** **Tabularium v2 is the store.** The Python v1 server (`mcp__tabularium-mcp__*`) is a read-only legacy archive. Nothing loads at session start. Recall on demand with `memory_recall`, passing the role's `audience` (decider, builder, reviewer or navigator), when prior decisions or gotchas bear on the task; `mcp__tabularium-mcp__recall` and `mcp__tabularium-mcp__decisions_query` stay as the fallback. The only save path is the T3 Code tool `memory_propose`: `kind` ("decision", "fact" or "defect"), `headline` (the claim in one sentence, under 100 characters), `claim`, `rejected` (the alternative ruled out; a decision needs it), the defect fields (`where`, `trigger`, `left_because`), optional `audience` and `stage`, and `origin` ("agent"). A defect saves at once as an open defect, with no tile, unless it carries `closes` or lands near an existing record; those, and every fact and decision, queue a tile and persist only when the owner approves it. Propose gotchas, decisions and defects only, never status or session narrative. A requirement or design for something not yet built is not a memory; it goes in the brief. The v1 write tools no longer exist, so a session that still lists a v1 `save` tool is talking to a stale server and must not call it. **Scope is not the repo name** (pairs collapse); `~/Projects/skillbook/hooks/scope-map.sh` is the mapping, and hooks and `memory_recall(scope=)` pass the resolved scope.
- **v1 dedup gate (retired).** The bounce protocol (bounced outcomes, `exits`, the distinct-confirmation call, the guard flag, `parked`) belonged to v1 `save`. `memory_propose` returns `flags` (what its checks found) and `neighbours` (close saved records) as evidence only. Read them, then fix or drop the proposal. A tile needs the owner's approval; a defect with no `closes` and no close record saves without one.
- **Cite substance, never bare ids.** When a Tabularium record id, or a label from a brief, grill or roadmap (D15, Q6, scope 3.2, the baseline), appears in a reply, carry what it says inline — a one-line paraphrase or the operative clause. The owner cannot see what sits under an id; a bare `0bec7b13` is a gap they have to guess across. Applies to every id, every time, including ids the owner already knows.
- **Notebook rule.** Transient notes (grill recommendations, blockers, tooling observations) go to `~/.claude/notebook.md` (user-scope) or `~/.claude/projects/<encoded>/notebook.md` (per-project). Skills don't auto-append — user says "save to notebook", assistant appends per `~/.claude/NOTEBOOK.md`.
- **Cross-stack partner.** Each repo's CLAUDE.md names its partner; the project index (repositories, Tabularium scopes, partners) lives in `Projects/CLAUDE.md`.

## Unslop — all prose, always

Applies to every artifact and every reply: specs, ADRs, SKILL.md, recon reports, commit and PR
text, conversation. Applies to main and to every dispatched agent. After drafting, ask "what still
marks this as AI-generated?" and fix what is left.

Exempt: `LANGUAGE.md` vocab (module, interface, seam, adapter, depth, leverage, locality, port,
surface) is mandated terminology, never softened to "component", "boundary" or "API". Exact field
names, command snippets and quoted output stay verbatim.

The 31-pattern list lives in the `unslop` skill — `~/.claude/skills/unslop/SKILL.md`; dispatched agents read it by path. Index: puffery, promotional adjectives, AI vocabulary (delve, pivotal, testament, …), superficial -ing tails, "not just X but Y", rule of three, false ranges, synonym cycling, em-dash monotony (same interrupt-and-restate 3× in one paragraph — the character itself is fine), colon as connector, Title Case headings, curly quotes, decorative emoji, chatbot phrases, sycophancy, filler, stacked hedges, abstract metaphor nouns, feeling instead of mechanism, dense sentences, passive voice, adverbs on weak verbs, the fancy synonym.

## Mattpocock vocab (quick-ref)

Architecture talk uses these terms exactly — no substitutes like "component," "service," "API," or "boundary."

- **module** — anything with an interface and an implementation (function, class, package, slice). Scale-agnostic.
- **interface** — everything a caller must know: types, invariants, ordering, error modes, config. Not just the type signature.
- **depth** — leverage at the interface: lots of behaviour behind a small interface. Deep = high leverage; shallow = interface nearly as complex as the implementation.
- **seam** — where an interface lives; a place behaviour can be altered without editing in place. (Not "boundary.")
- **adapter** — a concrete thing satisfying an interface at a seam. Role, not substance.
- **leverage** — what callers get from depth: capability per unit of interface learned.
- **locality** — what maintainers get from depth: change, bugs, knowledge concentrate at one place.

Full definitions, principles (deletion test, "interface is the test surface," one-adapter-vs-two), and concrete examples in `~/.claude/LANGUAGE.md`. Load that file at the start of any skill that proposes or critiques architecture.
