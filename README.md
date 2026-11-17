# skillbook

The instructions and workflows I use with Claude Code and Codex, kept in one repository.

It contains skills for investigating and implementing changes, agent roles for delegating work, and hooks and scripts that connect those practices to the tools. It also versions commands, output style, theme, `settings.json` and global instruction files. `~/.claude` is a set of symlinks into a checkout of this repo, so editing a file here changes the live configuration.

## How this fits

Skillbook defines how agents work. [Tabularium](https://github.com/simkaz12/tabularium) supplies persistent memory; my [T3 Code fork](https://github.com/simkaz12/t3code) exposes its current memory tools and memory tray. Memory integration is optional when adopting the configuration.

[Pi Assistant](https://github.com/simkaz12/pi-assistant) documents the homelab and additional agent tools used elsewhere in the setup.

This is a sanitized public copy. Client and employer names, ticket keys, people, hostnames, addresses and credentials were replaced or removed, and a few skills that only made sense for one client or one home server were dropped. The structure and the mechanisms are unchanged. Stand-ins used throughout: `crm-api` and `crm-web` are a fictional Laravel API and Nuxt SPA pair, `PROJ-123` is a Jira-style ticket key, `memory.example.internal` is the memory server, and `<owner>` is a GitHub account. Some project files (for example `skills/land/projects/crm.md`) were rewritten as short examples of the per-project mechanism rather than copied.

## Contents

- Layout
- Delegation tiers
- How a piece of work flows
- Hooks
- Memory
- Per-project additions
- Corpus capture
- Codex mirror and MCP sync
- Install and doctor
- Tests
- Third-party material
- Known rough edges

## Layout

| Path | What it is |
| --- | --- |
| `GLOBAL-CLAUDE.md`, `GLOBAL-CORE.md` | The global instructions. `GLOBAL-CLAUDE.md` is linked to `~/.claude/CLAUDE.md` and imports `GLOBAL-CORE.md`, which holds the rules shared with Codex. |
| `LANGUAGE.md`, `CONTEXT-LOAD.md`, `NOTEBOOK.md` | Architecture vocabulary, the on-demand context loading note, and the notebook protocol. |
| `LARAVEL-STANDARD.md`, `PYTHON-STANDARD.md`, `CODEX-TAIL.md` | Coding standards that `hand-do` and `spec-reviewer` read for a Laravel or Python repo, and the tail appended to Codex's `AGENTS.md`. |
| `agents/` | Five subagent definitions: `bolt`, `hand-ex`, `hand-do`, `spec-runner`, `spec-reviewer`. |
| `agent-projects/` | Per-project additions for agents, keyed by scope or repo name. |
| `skills/` | 25 skills, each a directory with a `SKILL.md`, plus `skills/README.md` as the index. |
| `commands/` | Slash commands: `/baseline`, `/flag`, `/good`. |
| `hooks/` | Hook scripts and the scope map they share. |
| `scripts/` | `install.sh`, `doctor.sh`, `sync-codex.sh`, `sync-mcp.sh`, `pull-base.sh`, `skill-project.sh`, `test-baseline.py`, `corpus-check.py`, `build-site.py`, `dev-ports.sh` and their tests. |
| `corpus-tools/` | `corpus_capture`, the Python package behind the capture hooks. |
| `codex/`, `mcp/` | The Codex hook registration and the MCP server list. |
| `output-styles/`, `themes/`, `statusline-command.sh`, `settings.json` | An output style, a colour theme, the status line, and the settings file. |
| `site/` | Source for a generated one-page intro site, with its redaction list and vendored assets. |
| `docs/reference.md` | The original operational README: install details, base-branch script, Codex mirror, MCP sync, per-project additions. |

## Delegation tiers

`GLOBAL-CLAUDE.md` defines who does what. The main session dispatches and the agents work.

| Tier | Model | Role |
| --- | --- | --- |
| main | the session's own model | Conversation, grilling, specs, memory, dispatch, and synthesis of what agents return. It does not edit code, drive a browser or search at scale. |
| `hand-ex` | Sonnet | Read-only explorer. Traces real code and data flow, reproduces bugs in a browser, returns verified findings. |
| `hand-do` | Sonnet | Builder for one bounded task. Implements, runs the project's own tests, runs a simplify pass, returns a verdict that carries a `review: required` or `review: exempt` flag. It never commits and never runs Codex. |
| `bolt` | Haiku | Mechanical scout for one narrow question: a file or symbol lookup, a caller search, a screenshot, a git log dig, a doc fact. Several run in parallel. |
| `spec-runner` | Sonnet | Executes a finished brief from `to-spec`, scope by scope, and returns a fenced verdict. |
| `spec-reviewer` | Sonnet, plus Codex | The review gate. Runs the Codex adversarial review, rules on each finding, checks each done scope and the running app, and returns PASS or FAIL. |

The Codex rule is that main never runs Codex. After a `spec-runner`, or after a `hand-do` that returned `review: required`, main dispatches `spec-reviewer`, which runs Codex and adjudicates its findings. A `review: exempt` result skips the gate. Scout claims that feed a decision get confirmed with one decisive command before main acts on them. Standing rules live in files (an agent's definition or its `agent-projects` addition), because the agent definition outranks recalled memory inside the subagent.

`scripts/sync-codex.sh` generates Codex TOML agents from the same `agents/*.md` files, so the roles exist under both CLIs.

## How a piece of work flows

The skills form a path. A piece can skip stages, but skipping is meant to be a choice. `site/principles/flow-of-work.md` and `site/principles/review-gates.md` hold the reasoning.

1. `flow` keeps one piece in one thread and picks the smallest next step that removes a named uncertainty. It does not replace the skills below; calling them directly still works.
2. `recon` is a reconnaissance pass: gather the context the next decision needs, read-only, starting narrow and widening only for a named gap. Its entry point takes a ticket key because most of its use is on work tickets, but the principle applies to any change. `diagnose` does the same for a hard bug.
3. `grill-me` questions the owner until requirements and design choices have a shared shape. `grill-with-docs` also writes the glossary and the hard calls into the repo.
4. `to-spec` turns the agreement into a solo or split execution brief, with scopes, verify steps and an out-of-scope line. Work too large for one session goes to `wayfinder`, which maps it as decision tickets.
5. `spec-runner` runs the brief. In a split brief, one runner per independent lane runs in waves, and an integrate-mode runner finishes.
6. `spec-reviewer` gates the result: Codex review, per-scope checks, a live look at the app.
7. `verify-ticket` checks the delivered change against its acceptance criteria with focused tests and a real run. The full suite is not its job.
8. `land` commits, pushes and opens the PR in the repo's convention, gated on a current verify proof. `zero` goes further for personal repos: merge, pull the build branch, rebuild.

Around the path sit `preflight` (drive the running app against four slips a green suite hides), `blast-radius`, `review-structure` (an explorer, not a gate), `debate` (a Claude seat and a Codex seat on one subject), `qa-ticket` (testing a teammate's ticket), `how-to-test`, `playwright`, `reflect`, `cleanup`, `flow-eval`, `write-a-skill`, `improve-codebase-architecture`, `unslop`, `what`, and `typesafe-ai`. `skills/README.md` has a one-line entry for each and a log of skills that were removed and why.

The full test suite runs once per ticket, in the background, started by `spec-reviewer` on a PASS and awaited by `land`. `scripts/test-baseline.py` (`/baseline`) diffs that run against a snapshot of already-failing tests, keyed by the merge-base commit, so a red base does not hide a real regression.

A quick fix is an owner-triggered exception: main edits inline, one `hand-ex` verifies, and nothing lands.

## Hooks

Registered in `settings.json`:

| Event | Script | What it does |
| --- | --- | --- |
| `PreToolUse` on Bash | `bashfilter-chain` (optional external binary) | Runs a command filter when the binary exists and is executable; otherwise passes the command through. The binary is not part of this repo. |
| `SessionStart` | `hooks/base-branch-check.sh` | Reads the repo's base branch from `hooks/scope-map.sh`, runs `pull-base.sh --check`, and tells the session if the repo is behind `origin`. |
| `SubagentStart` | `hooks/load-agent-additions.sh` | Resolves the repo and scope from `cwd`, and injects the matching `agent-projects/<key>/<agent>.md` and `testing.md` under a "Project additions" header. It never exits non-zero. |
| `UserPromptSubmit`, `Stop`, `SessionEnd`, `UserPromptExpansion` | `corpus-tools/corpus_capture/capture_hook.py` | Appends one redacted envelope line per event to a local day file. See "Corpus capture". |

`codex/hooks.json` registers the `SubagentStart` additions hook for Codex.

Two more scripts, `hooks/load-tabularium-context.sh` (session start) and `hooks/load-tabularium-role-context.sh` (subagent start), fetch grounding from the memory server. They are in the repo with tests but this `settings.json` does not register them; the current rule in `GLOBAL-CORE.md` is that nothing loads at session start and agents recall on demand. `hooks/test-scope-map.sh` and `hooks/test-agent-additions.sh` test the shared pieces.

`scripts/install.sh` sets `core.hooksPath` to `.githooks`, whose `pre-commit` runs `scripts/corpus-check.py`. That checker looks for dangling skill and agent references, calls to retired tools, and fork/allowlist mismatches, with a waiver file for deliberate mentions.

## Memory

Memory lives in [Tabularium](https://github.com/simkaz12/tabularium). Its v1 MCP server is a read-only archive; current v2 memory tools reach a separate HTTP server through my [T3 Code fork](https://github.com/simkaz12/t3code). What is here is how the configuration uses them.

- Recall on demand. `GLOBAL-CORE.md` says nothing loads at session start. Main and each subagent call `memory_recall` (the T3 Code tool) with an `audience` of `decider`, `builder`, `reviewer` or `navigator`. `hand-do` recalls as builder, `hand-ex` as navigator, `spec-reviewer` as reviewer, main as decider. Records with no audience come back for every role.
- The older server (`mcp__tabularium-mcp__recall`, `decisions_query`, `decision`) is a read-only legacy archive and a fallback.
- Saving goes through `memory_propose` only, with `kind` (decision, fact or defect), a short headline, the claim, and for a decision the alternative that was rejected. Agents never propose. They list what is worth keeping in a `### Memory` block of their return, and main files it. The instructions in this public snapshot ask for owner approval before saving facts or decisions; a defect saves directly unless it closes or sits near an existing record. In current v2, agent proposals normally apply immediately; a close fact or decision can be held for a fold ask. See [Tabularium v2](https://github.com/simkaz12/tabularium#v2) for the current behavior.
- Scope is not the repo name. `hooks/scope-map.sh` maps a checkout path to a scope, and pairs collapse: in the shipped example `crm-api` and `crm-web` both map to `crm`. The same file gives each repo's base branch. Memory recall passes the resolved scope.
- `mcp/servers.json` lists the memory server and a Playwright server for every project, and project-scoped servers for named repos. `scripts/sync-mcp.sh` copies them into `~/.claude.json`. The `headersHelper` path in the example points at a script that prints auth headers; it is not included.

## Per-project additions

A project's changes to a personal skill or agent live here, keyed by scope or repo, so nothing is written into project repos.

| Target | File |
| --- | --- |
| Skill | `skills/<skill>/projects/<scope or repo>.md` |
| Agent | `agent-projects/<scope or repo>/<agent>.md` |

A skill pulls its files in through a `## Project additions` section that runs `scripts/skill-project.sh <skill>`. Agents get theirs from the `SubagentStart` hook. `agent-projects/<scope>/testing.md` holds the `focused:` and `full:` test commands that `hand-do`, `spec-reviewer`, `verify-ticket`, `land` and `test-baseline.py` use. The `crm` files show the opt-out case: a repo that does not follow the shared Laravel standard says so in its `hand-do`, `spec-runner` and `spec-reviewer` additions. Details are in `docs/reference.md`.

## Corpus capture

`corpus-tools/corpus_capture` is a small logging pipeline for the owner's own sessions. The hook writes one JSON line per prompt, stop, session end and slash command into a local day file under `~/.claude/capture` (or `$CORPUS_CAPTURE_DIR`). Prompt text passes through `redact.py` first, which masks vendor-prefixed keys, JWTs and high-entropy strings. `/flag` and `/good` are label commands: the hook records the label and blocks the prompt so it never reaches the model. There is also a sweep, a backup script, a health report and an export for a second personal assistant's messages. Nothing leaves the machine except through the backup script's rsync target, which is a placeholder here.

## Codex mirror and MCP sync

`scripts/sync-codex.sh` makes `~/.codex` mirror this repo: `AGENTS.md`, `hooks.json`, skill symlinks, and agent TOML generated from `agents/*.md`. It never touches `config.toml` or `auth.json`, and it moves stray real directories aside instead of deleting them. `scripts/sync-mcp.sh` is a mirror-mode copy of `mcp/servers.json` into `~/.claude.json`, with a timestamped backup before any change. Both support `--dry-run`. Details are in `docs/reference.md`.

## Install and doctor

```bash
git clone <repo-url> ~/Projects/skillbook
bash ~/Projects/skillbook/scripts/install.sh
```

Prerequisites are `git`, `python3` and `jq`. `bashfilter` and a reachable memory server are optional; the installer warns and carries on without them. `install.sh` creates `~/.claude`, links each entry (agents, commands, hooks, output styles, skills, themes, `settings.json`, the status line, the instruction files, `corpus_capture`) into the clone with a backup of anything already there, sets `core.hooksPath`, runs the Codex and MCP syncs when applicable, and ends with `doctor.sh`. `--dry-run` prints the plan and `--no-doctor` skips the closing check. Hook scripts default `PROJECTS_ROOT` to `$HOME/Projects`.

`scripts/doctor.sh` is a read-only check with seven sections: A skill frontmatter, B agent frontmatter, C the projection into `~/.claude`, D the projection into `~/.codex`, E drift between `mcp/servers.json` and `~/.claude.json`, F skills that have a `projects/` directory but no resolver line, G agent additions that name no agent. It exits non-zero on any problem.

## Tests

- `python3 -m unittest discover -s scripts/tests` covers the site builder and the baseline tool.
- `python3 -m unittest discover -s skills/flow-eval/tests` covers the flow-comparison runner.
- `bash hooks/test-scope-map.sh`, `bash hooks/test-agent-additions.sh`, `bash scripts/tests/test_pull_base.sh`.
- `python3 scripts/corpus-check.py --self-test`.
- `python3 scripts/build-site.py --out /tmp/index.html` builds the intro site and fails if its redaction list leaves a leak.

`agent-projects/skillbook/testing.md` lists the same set as this repo's own focused and full commands.

## Third-party material

Most of the text is the owner's. Some is not, and each such file carries a provenance line at the top. `THIRD_PARTY_NOTICES.md` has the full list and the license texts.

- Derived from Matt Pocock's skills (MIT): `wayfinder`, `what`, `diagnose`, `grill-with-docs`, `improve-codebase-architecture`, and `LANGUAGE.md`. `grill-me`, `to-spec` and `write-a-skill` share names and concepts but are rewrites.
- Derived from pstack by Lauren Tan (MIT): `unslop` and `blast-radius`. `reflect` borrows the idea and adapts two reviewer files, and `review-structure` takes its seven concerns from pstack's principle skills.
- `typesafe-ai` is TypeSafe AI's vendor skill, kept with its own MIT `LICENSE`.
- `site/vendor` holds marked (MIT) and two fonts under the SIL Open Font License, each with its license.
- Tools this configuration calls but does not include: Claude Code, Codex CLI and its plugin, Playwright MCP, T3 Code, and the Tabularium server.

## Known rough edges

- Several skills still take a Jira-style ticket as their input (`recon`'s entry point, `qa-ticket`, parts of `land`) and a Docker-based Laravel stack. The `crm` project files show where that assumption is configured.
- The memory-context hooks are kept but unregistered, as noted under Hooks.
- Settings, hooks and skills reference tools such as `mcp__t3-code__memory_recall` and `mcp__jira__jira_tool`. They exist only on a machine running those MCP servers.

