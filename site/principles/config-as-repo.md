---
title: Config as repo
covers: scripts/*, hooks/scope-map.sh, hooks/load-agent-additions.sh, skill/cleanup, skill/flow-eval, skill/write-a-skill, command/flag, command/good, doc/GLOBAL-CLAUDE.md
---

The authored part of `~/.claude` lives in this repository. Each item is symlinked back into place, so editing a file here edits the live configuration, and `git pull` on another machine is the whole sync.

## Symlinks, one item at a time

Skills, agents, commands, hooks, themes, output styles, `settings.json`, the status line script and the global rules files are linked individually. Runtime state stays outside the repo by construction. That state is about 2.4 GB of history, captures and credentials. With per-item links the `.gitignore` does not have to be an allowlist guarding a credential, because the credential is never inside the tree.

Two alternatives were rejected. One was a repository initialised inside `~/.claude` itself, which wraps git around auth tokens and machine state, one missed ignore rule from committing a secret. The other was linking `~/.claude` wholesale, which has the same exposure. The global rules file is stored as `GLOBAL-CLAUDE.md` because Claude Code collects every `CLAUDE.md` it finds walking up from the working directory, and a root-level one would load the same text twice as this repository's own project memory.

`scripts/install.sh` creates the links, backs up whatever sat there before, sets the pre-commit hook path and runs the sync scripts. `scripts/doctor.sh` checks that everything resolves. Both are safe to run again.

## Mirrors

Codex gets a mirror, not a copy. `scripts/sync-codex.sh` links skills into `~/.codex/skills`, symlinks the hooks file and generates agent definitions from the Markdown agents. It prunes by moving, never by deleting, and it asserts afterwards that every skill name resolves, so a partial mirror fails loudly. Codex hook commands reference `$HOME/.claude/hooks`, so the same scripts serve both tools.

MCP servers cannot be symlinked because `~/.claude.json` is rewritten constantly and also holds OAuth and history. `scripts/sync-mcp.sh` copies the servers from `mcp/servers.json` in mirror mode, backs the file up before any change and writes through a temp file. The [Wiring](#/wiring) page shows the result.

## Project additions

A project's difference from a skill or agent lives here, keyed by a memory scope or a repository name, and is only appended. The base never names a project. `scripts/skill-project.sh` resolves the files for a skill, and `hooks/load-agent-additions.sh` does it for agents. Copying additions into each repository would need a sync step and dirty those repositories. A same-named project skill would be shadowed by the personal one, which is what left one fork dead.

## The checker

`scripts/corpus-check.py` runs as the pre-commit hook. It finds dangling skill references, calls to retired memory tools, forks into agents that lack the needed tools and dangling agent names. Waivers live in a text file and each needs a reason. The script is also how this site decides what counts as a skill, agent or command name.

## Housekeeping

`cleanup` sweeps finished local artifacts at the end of a day. `flow-eval` compares two versions of a flow on frozen cases and is for changing a flow, not for daily work. The `flag` and `good` commands are labels for the corpus capture pipeline, which this site leaves out.
