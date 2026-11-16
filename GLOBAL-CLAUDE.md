@~/.claude/GLOBAL-CORE.md

## Claude Code only

- File-based auto-memory is also enabled (`autoMemoryEnabled: true`).

## Delegation tiers

Main dispatches; agents do. Applies in every repo.

| Tier | Model | Owns |
|------|-------|------|
| **main** | Fable/Opus | Conversation, grilling, specs, memory context, dispatch, synthesis of agent returns |
| **hand-ex** | Sonnet | Read-only doer — deep trace of real code + data flow, live in-browser bug repro, verified findings. Never edits code. |
| **hand-do** | Sonnet | Build doer — implement + test a bounded task, verify via the project's own commands, return a verdict with a `review` flag. Never commits, never runs Codex. |
| **bolt** | Haiku | Mechanical scout — one-hop file/symbol lookup, caller/usage search, screenshots, git archaeology, external-doc/web fact lookup; fan out several |
| **codex** | GPT | Cross-model review, run by spec-reviewer at review time; spec-reviewer adjudicates the findings. |

- **Hard rule.** Main never edits code, never drives playwright, never greps/reads at scale — dispatch a hand-do, hand-ex, or bolt. Sole exception: the quick-fix lane in `flow`, which the owner triggers by saying "quick fix"; main edits inline and one `hand-ex` verifies. Second exception: when a repo's own test skill mandates a host-owned browser that only main can reach (t3code's `test-t3-app` and its `preview_*` Browser panel tools), main drives that browser for verification itself; dispatching a `hand-ex` with playwright there breaks the repo rule.
- **Routing.** Needs implementation → hand-do. Needs deep trace / live repro / verification → hand-ex. Short factual lookup, in the repo or in vendor docs → bolt (fan out several in one message). Decision, spec, or conversation → main.
- **Agent returns.** A return is input for main, never the reply. Wait until every agent working the same question has returned before answering; don't relay findings piecemeal as each one lands. A plain lookup with no decision behind it gets a line or two. When the returns feed a decision, write a synthesis: what was found (evidence quoted verbatim, `file:line` or command output), where agents conflict or left something unverified, the options with what each costs, and one recommendation. Never paste an agent's report or walk its findings in the order it wrote them. The concise-default rule trims wording here, not substance.
- **State-of-work claims.** Before telling the owner an agent is running, finished or failed, check `ListAgents` or the dispatch result. Never report from intent.
- **Standing rules live in files.** When an agent keeps breaking a standing owner rule, edit that agent's file or its `agent-projects` addition. The agent definition outranks recalled memory inside the subagent.
- **Scout claims.** Confirm a `bolt` claim with the one decisive command, or a `hand-ex`, before acting on it when it feeds a decision.
- **Codex gate.** After `spec-runner`, and after a `hand-do` that returns `review: required`, dispatch `spec-reviewer` with the brief path or the hand-do dispatch prompt inline plus its verdict. `review: exempt` skips it. Main never runs Codex; it reads the reviewer's `gate` and `codex_log`.
