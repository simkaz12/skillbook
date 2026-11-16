---
title: Skillbook
route: skill/recon, skill/grill-me, skill/to-spec, agent/spec-runner, agent/spec-reviewer, skill/verify-ticket, skill/land
gates: agent/spec-reviewer, skill/verify-ticket
branch: skill/wayfinder
branch_from: skill/grill-me
coordinator: skill/flow
---

Skillbook is the repository behind one person's Claude Code setup. Skills, agents, slash commands, hooks, settings and the global rules file all live in it, and `~/.claude` is a set of symlinks into a checkout. Editing a file here edits the live configuration. This site is a generated reading copy of that repository, built into one HTML file so it can be sent to someone without a clone.

The setup exists to make one workflow repeatable. The owner talks to a main session. Main never reads code at scale or edits it. It dispatches small agents with a bounded brief and reads their verdicts. Work moves through investigation, agreement, execution, review and verification, and a skill covers each step, so no step relies on a session remembering to do it. Memory sits outside the repository in Tabularium, which main reads on demand with `memory_recall` and writes only through `memory_propose` tiles the owner approves.

Six principle articles explain why the setup looks like this.

- [Delegation tiers](#/principle/delegation-tiers) covers who does what, and which tools each agent gets.
- [Flow of work](#/principle/flow-of-work) covers the path from a vague ticket to landed code.
- [Review gates](#/principle/review-gates) covers who checks the work and what each check is allowed to run.
- [Memory](#/principle/memory) covers Tabularium, scopes, deduplication and reflection.
- [Prose rules](#/principle/prose-rules) covers how text is written, and the vocabulary for architecture talk.
- [Config as repo](#/principle/config-as-repo) covers symlinks, the Codex mirror and the pre-commit checker.

Every other article describes one file. A skill article shows its frontmatter in the infobox and its body as written. A hook or script article shows the source. The infobox on each page lists the principles that cover it, and the "What links here" list at the bottom shows who refers to it. The [Wiring](#/wiring) page shows which script runs on which event.

Names in backticks, such as `flow` or `hand-do`, are links. A plain word is not. Where a link points at something this site leaves out, such as the corpus capture hook, the page says so. Machine addresses, usernames and ticket numbers are replaced when the page is built, so a few strings read as placeholders.

Start with the [Skills index](#/skills/README.md) if you want the catalogue, or with `flow` if you want to see how a piece of work starts.
