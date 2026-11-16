# skillbook

Claude Code config as a repo: skills, agents, commands, hooks, output styles, themes, `settings.json` and the global `CLAUDE.md`. `~/.claude` is a set of symlinks into this checkout, so editing here is editing the live config.

## Setup on a new machine

The clone can live anywhere — every script derives the skillbook path from its own location, and nothing in the live config points at a fixed path or username.

Prerequisites: `git`, `python3`, `jq`, network access to a Tabularium MCP server. `bashfilter` is optional (see below).

```bash
git clone <repo-url> ~/Projects/skillbook && bash ~/Projects/skillbook/scripts/install.sh
```

`install.sh`:

- creates `~/.claude` and `~/.claude/corpus-tools` if missing;
- links every farm entry (agents, commands, hooks, output-styles, skills, themes, settings.json, statusline-command.sh, CONTEXT-LOAD.md, LANGUAGE.md, NOTEBOOK.md, CLAUDE.md, GLOBAL-CORE.md, corpus-tools/corpus_capture) into the clone, backing up any real file or directory already sitting at that path;
- sets `core.hooksPath` to `.githooks` in the clone;
- warns, without failing, if `bashfilter`, `python3`, `jq`, or Tabularium is missing or unreachable;
- runs `scripts/sync-codex.sh` when `~/.codex` exists;
- runs `scripts/sync-mcp.sh` to put the MCP servers into `~/.claude.json` (a failure warns, it never fails the install);
- runs `scripts/doctor.sh` to confirm the farm resolves cleanly.

Run it again any time to pick up a new farm entry or repair a broken link; `--dry-run` shows the plan without changing anything, `--no-doctor` skips the closing doctor run.

The `PreToolUse` hook in `settings.json` runs `$HOME/.local/share/bashfilter/bin/bashfilter-chain` on every Bash call when that binary is executable, and passes the command through untouched otherwise. Install bashfilter for command filtering; without it, Bash calls just run normally.

The Tabularium MCP server and the session-start grounding hook both talk to `memory.example.internal:8787`; when that host is unreachable, sessions start without memory context and the `tabularium-mcp` server shows as failed.

The grounding hooks default `PROJECTS_ROOT` to `$HOME/Projects`. Claude Code inherits the environment of the shell it's launched from, so a machine that keeps repos elsewhere exports `PROJECTS_ROOT` in its shell profile.

Optional, Codex CLI: see "Codex mirror" below.

## Base branch

`scripts/pull-base.sh [--repo <path>] [--backup-dir <dir>] [--key <slug>] [--check] [--no-switch]` fast-forwards a repo to `origin/<base>`; `hooks/scope-map.sh` (`base_branch`) knows each repo's base. Before it reverts any dirty file it writes the dirty diff to a backup patch, then it reapplies the files the pull touches with `git apply --3way`. It never stashes, merges or rebases. Exit 0 means current or pulled. Exit 3 means it refused and changed nothing (no base on file, operation in progress, detached HEAD, local-only commits, untracked or ignored files where upstream adds a file, a backup file that already exists, a file out of the index or replaced by a directory on disk where upstream changes it, fetch failure). Backup patches, including one for staged versions, are never overwritten. Exit 4 means the pull happened but reapplying left conflict markers or failed outright; the report names the files and the backup path. `--check` only reports counts, and `--no-switch` fast-forwards the local base ref without leaving the current branch. `hooks/base-branch-check.sh` runs the check at SessionStart and tells the session when its repo is behind. `bash scripts/tests/test_pull_base.sh` covers both.

## Codex mirror

`scripts/sync-codex.sh` makes `~/.codex` mirror this repo for Codex CLI, the way `~/.claude` already does for Claude Code via symlinks.

**Owns:** `~/.codex/AGENTS.md`, `~/.codex/hooks.json` (symlink into `codex/hooks.json`, whose commands reference `$HOME/.claude/hooks/*` — Codex runs command hooks through `$SHELL -lc`, so `$HOME` expands the same way it does under Claude Code), `~/.codex/skills/*` (symlinks into `skills/`), `~/.codex/agents/{bolt,hand-do,hand-ex,spec-runner,spec-reviewer}.toml` (generated from `agents/*.md`).

**Never touches:** `~/.codex/config.toml`, `~/.codex/auth.json`, `~/.codex/skills/.system`, any other file under `~/.codex/agents/`.

**Prune, never delete.** A real directory under `~/.codex/skills/` that isn't a skillbook skill moves to `~/.codex/skills.pruned-YYYYMMDD/`. A regular file sitting at a skillbook skill name moves there too, suffixed `.HHMMSS` to survive same-day collisions. A pre-existing real `~/.codex/AGENTS.md` or `~/.codex/hooks.json` gets backed up before the script overwrites or unlinks it, every time, no skip-if-exists check — backup names carry a to-the-second timestamp (`.bak-YYYYMMDD-HHMMSS`), so two hand-edits in one day get two backups instead of one silently swallowing the other.

**Mirror completeness.** After linking, the script asserts every skillbook skill name resolves to a symlink under `skills/`. Any offender prints as `missing: <path>` and the run exits 1 instead of leaving a partial mirror.

Run `bash scripts/sync-codex.sh --dry-run` first to see the plan, then `bash scripts/sync-codex.sh`. Re-running on a clean tree prints nothing.

For Codex models, `sol` and `luna` in agent source are family selectors. Sync uses `jq` to select the newest numeric version among visible models in `$CODEX_HOME/models_cache.json` and writes the real model ID into each TOML file. Missing or unusable catalogs stop sync rather than pinning an older model. Refresh the catalog through Codex, run `bash scripts/sync-codex.sh --agents-only`, then reload Codex to refresh native roles. T3 dispatch selects from its current provider catalog. Main's model setting remains a session choice.

**One-time `config.toml` stanza** (not written by the script — it holds tokens):

```toml
[mcp_servers.tabularium-mcp]
url = "http://memory.example.internal:8787/mcp"
enabled_tools = ["recall", "decision", "decisions_query", "context"]
```

Codex's Tabularium access is read-only: `enabled_tools` allowlists the read tools and leaves `save` and every other write unreachable.

`project_doc_fallback_filenames = ["CLAUDE.md"]` (top-level key, same file) makes Codex read a repo's `CLAUDE.md` as its project doc when that repo has no `AGENTS.md`.

**Trust step, once per hook-script change.** Run `codex`, then `/hooks`, and approve the `SessionStart` entry (Tabularium grounding) and the `SubagentStart` hooks.


## MCP servers

MCP servers live in `~/.claude.json`, which Claude Code rewrites constantly and which also holds OAuth, history and per-project state. It can't be symlinked, so `scripts/sync-mcp.sh` copies the servers in from `mcp/servers.json`.

`mcp/servers.json` has two keys. `user` maps server names to their config and lands in the top-level `mcpServers`. `projects` maps a directory name to the servers that repo gets, and lands in `projects[$PROJECTS_ROOT/<name>].mcpServers`. `PROJECTS_ROOT` defaults to `$HOME/Projects`. A listed project whose directory doesn't exist on the machine is skipped without output.

**Owns:** top-level `mcpServers`, and `mcpServers` inside each project entry that is a direct child of `$PROJECTS_ROOT`.

**Never touches:** any other field in `~/.claude.json` or in a project entry, project keys outside `$PROJECTS_ROOT`, and deeper paths such as worktrees.

**Mirror mode.** The file is the source of truth. A server missing from `servers.json` is removed, and a direct child of `$PROJECTS_ROOT` that isn't listed ends up with no servers. Before any change the script copies `~/.claude.json` to `~/.claude.json.bak-YYYYMMDD-HHMMSS`; a run with nothing to change writes no backup. Writes go through a temp file in the same directory and keep the original mode.

**Rendering.** `$HOME` is expanded inside every string value when the script runs. A `command` without a `/` is resolved with `command -v` and written as an absolute path, so a desktop launch without mise on `PATH` still finds it. If the command isn't found, the script prints `error: <scope>/<server>: <cmd> not found on PATH`, exits 1 and writes nothing.

`bash scripts/sync-mcp.sh --dry-run` prints the plan (`<scope>: add|update|remove <server>`) and changes nothing. Without the flag it prints the same lines plus `backup: <path>`. A clean state prints nothing.

`scripts/doctor.sh` section E runs the dry-run and reports every plan line as drift, so a Node upgrade that moves `npx` shows up there until the script runs again.

## Per-project additions

A project's delta to a personal skill or agent lives in skillbook, keyed by a Tabularium scope or a repo name; nothing is written into project repos, so `git pull` is the whole sync. `<repo>` is the directory name of the main checkout, the same key `mcp/servers.json` uses under `projects`. `<scope>` is what `hooks/scope-map.sh` maps the main checkout's path to, so `crm` covers `crm-api` and `crm-web`. The two Tabularium hooks use the same mapping.

Files for a project load scope first, then repo, separated by a blank line. A repo whose name equals its scope loads once. Put shared content under the scope and repo-only content under the repo.

| Target | File |
| --- | --- |
| Skill | `skills/<skill>/projects/<scope or repo>.md` |
| Agent | `agent-projects/<scope or repo>/<agent>.md` |

**Skills.** A skill pulls its additions in through a `## Project additions` section at the end of its SKILL.md: a `` !`$HOME/.claude/skills/../scripts/skill-project.sh <skill>` `` line that Claude Code runs when the skill loads, plus `allowed-tools: Bash(*/skill-project.sh *)` in the frontmatter (without it a `claude -p` run denies the command and the skill fails to load), plus one sentence telling Codex, which doesn't run `!` injection, to run the command itself if it sees the raw line.

**Agents.** `!` lines in an agent file are not executed, so agents get their additions from `hooks/load-agent-additions.sh`, registered on `SubagentStart` in `settings.json` and `codex/hooks.json`. It reads `agent_type` and `cwd` from stdin, resolves scope and repo, and injects the matching files under a `Project additions (agent=..., scope=..., repo=...)` header. No match, no output. It is separate from the Tabularium role hook, so a Tabularium outage cannot touch it, and it never exits non-zero. Codex 0.158 passes `SubagentStart` hooks the same `agent_type` (the agent TOML `name`) and `cwd`, and `additionalContextLimit` is set per hook entry; a new Codex hook entry needs trusting once in `/hooks`.

The files live in `agent-projects/`, not `agents/projects/`: Claude Code scans nested directories under `.claude/agents/`, and `~/.claude/agents` is a symlink to `agents/`. A frontmatter-less file stayed hidden in a probe, but one that gained frontmatter would register as a phantom agent.

**Resolver.** `scripts/skill-project.sh <skill>` finds the repo from `git rev-parse --git-common-dir`, so subdirectories and worktrees resolve to the main checkout's name. It prints the scope file, then the repo file, or `none` outside git or without a match. It always exits 0, because a failing `!` command stops the skill from loading. It sits in `scripts/` so neither `doctor.sh` nor `sync-codex.sh` mistakes it for a skill.

**Shadowing.** A personal skill fully shadows a same-named project skill, so a fork under a repo's `.claude/skills/` is dead; move its delta here instead.

`scripts/doctor.sh` section F fails when a skill has a `projects/` dir but no resolver line or no matching `allowed-tools` line in its SKILL.md. Section G fails when an `agent-projects/<key>/<agent>.md` names no agent in `agents/`, or when `settings.json` does not register the hook. A key that is neither a directory under `$PROJECTS_ROOT` nor a scope in `hooks/scope-map.sh` prints an `info:` line, not a failure.
