<!-- Provenance: adapted from pstack (https://github.com/cursor/plugins/tree/main/pstack, MIT License, Copyright (c) 2026 Lauren Tan). See THIRD_PARTY_NOTICES.md. -->

# Tooling lens

Name the concrete tool, command, path, or flag detail a future agent would otherwise re-derive — the load-bearing technical fact that survives code drift.

Scan for:

- Tool invocations and command flags the agent had to discover
- Library or framework quirks: config, lockfiles, env-var behaviour, version-specific gotchas
- File and path conventions that aren't obvious at a glance
- Test commands, CI flags, and how to reproduce a failing run locally
- Debugging entry points: where logs land, which query to run, how to capture a trace
- Build, package-manager, or container surprises that cost minutes the first time

## Agent self-sufficiency

Flag every moment the user manually supplied context the agent could have fetched itself — via an MCP tool (Jira, GitHub, Bitbucket, Tabularium, laravel-boost, playwright) or a sibling skill.

- **Principle** — what the agent should have looked up automatically.
- **Evidence** — the user's manual hand-off: a pasted ticket title or description, a PR number, a log excerpt, a screenshot of something queryable, "this is from PR #X".
- **Routing** — the skill that owns the workflow this came up in. Extend it to call the tool so the next agent fetches the context itself.

The durable improvement is the skill learning to use the tools already granted to it, not this one user typing one less ticket ID.

Evidence for this lens includes the exact command, flag, or path in the quote.
