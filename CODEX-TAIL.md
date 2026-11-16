## Codex only

- Tabularium from Codex exposes `recall`, `decision`, `decisions_query`, and `context` only. The server exposes no write tool, so Codex never saves and does not report a reload as a fix. Proposals are main's job through `memory_propose`. `mcp__tabularium-mcp__recall` is Claude Code's name for the same `recall` tool.
- `~/.codex/skills/*` are symlinks into the skillbook clone's `skills/` directory, the same files Claude Code loads. Edits belong in skillbook, never in `~/.codex/skills/`.
- `~/.codex/agents/{bolt,hand-do,hand-ex,spec-runner,spec-reviewer}.toml` are generated from `skillbook/agents/*.md` by `scripts/sync-codex.sh`. Regenerate, never hand-edit.
- `~/.codex/AGENTS.md` is generated from `GLOBAL-CORE.md` + `CODEX-TAIL.md` by the same script.
- Per-repo `CLAUDE.md` is read as the project doc when the repo has no `AGENTS.md`; where both exist, `AGENTS.md` wins.

## Delegation tiers

Main dispatches; agents do. Applies in every repo.

| Tier | Model | Owns |
|------|-------|------|
| **main** | Latest Sol (high) | Conversation, grilling, specs/PRDs, memory context, dispatch, synthesis of agent returns |
| **hand-ex** | Latest Sol (high) | Read-only doer — deep trace of real code + data flow, live in-browser bug repro, verified findings; recon fans out a fleet. Never edits code. |
| **hand-do** | Latest Sol (high) | Build doer — implement + test a bounded brief, verify via the project's own commands, return a verdict. Never commits. |
| **bolt** | Latest Luna | Mechanical scout — one-hop file/symbol lookup, caller/usage search, screenshots, git archaeology; fan out several |

- **Hard rule.** Main never edits code, never drives playwright, never greps/reads at scale — dispatch a hand-do, hand-ex, or bolt. Sole exception: a trivial single-file edit the user explicitly asks for inline.
- **Routing.** Needs implementation → hand-do. Needs deep trace / live repro / verification → hand-ex. Short factual lookup → bolt (fan out several in one message). Decision, spec, or conversation → main.
- **Codex model selection.** Main, both hands and the spec roles use the newest available numeric `gpt-<version>-sol` model with high reasoning. Bolt uses the newest `gpt-<version>-luna`. Compare version parts numerically within the exact family; never substitute Terra, Astra or a dated variant. On T3, discover the current provider catalog with `orchestrator_capabilities` before the first delegation, choose the latest family member, and set `target.model` explicitly; Sol also sets `target.options.reasoningEffort: "high"`. Follow T3's catalog refresh rules. Native agent files resolve the `sol`/`luna` source selectors from the visible models in `$CODEX_HOME/models_cache.json` when `scripts/sync-codex.sh --agents-only` runs; reload Codex after syncing. Use explicit T3 dispatch when a loaded native role names an older model. Never pass the internal selectors as provider model IDs. Main's running model does not change in place; select the latest Sol with high reasoning when starting or configuring its session.
- **Agent returns.** A return is input for main, never the reply. Wait until every agent working the same question has returned before answering; don't relay findings piecemeal as each one lands. A plain lookup with no decision behind it gets a line or two. When the returns feed a decision, write a synthesis: what was found (evidence quoted verbatim, `file:line` or command output), where agents conflict or left something unverified, the options with what each costs, and one recommendation. Never paste an agent's report or walk its findings in the order it wrote them. The concise-default rule trims wording here, not substance.
- **No cross-model gate from this side.** The Codex review runs in `spec-reviewer.md` and is a Claude Code procedure; a spec-reviewer hosted here reports `gate: unavailable`, `gate_reason: codex-host`.
- Test commands live in `~/Projects/skillbook/agent-projects/<scope>/testing.md`. Run `focused:` commands only; the full suite belongs to `verify-ticket`.
