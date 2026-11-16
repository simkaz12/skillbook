---
name: cleanup
description: End-of-day sweep of finished local dev artifacts across all repos. Use when the user says "cleanup", "clean up", "tidy up", "end of day", "sweep artifacts", or asks to clear playwright screenshots/debris, drained plan-dirs, or finished QA dirs. NOT for refactoring or tidying source code — that is never this skill.
argument-hint: "(none) — run dry first, then confirm"
---

# Cleanup

Sweep finished artifacts off disk at end of day. Detection and disposition live in `cleanup.sh`; this file owns the policy and the safety gate.

## Protocol — never skip the gate

1. Run the dry-run: `bash ~/.claude/skills/cleanup/cleanup.sh`
2. Show the user the full `RM` / `MV` preview and the summary line.
3. Get explicit user confirmation. This gate holds when the skill fires on its own, not only when it is slash-invoked — never pass `--execute` in the same turn as the dry run.
4. Only then: `bash ~/.claude/skills/cleanup/cleanup.sh --execute`
5. After executing in a work repo that trashed anything, ensure `.trash/` is in that repo's `.gitignore`.

## What it touches

| Artifact | Where | Work repos | Personal (notes-app) |
|---|---|---|---|
| Screenshots + console/page debris | `.playwright-mcp/*.png,*.log,*.yml,*.webm,*.zip` | delete | delete |
| Drained plan-dir | `docs/superpowers/plans/<slug>/` with `tasks/` empty **and** `done/` non-empty | → `.trash/<date>/plans/` | → `docs/superpowers/backlog/plans/` |
| PRD for a drained plan | `docs/superpowers/specs/<slug>.md` (basename matches the plan) | → `.trash/` | → `backlog/specs/` |
| Finished QA dir | `docs/qa/<date>/` with `failed/` and `incomplete/` empty | → `.trash/<date>/qa/` | → `backlog/qa/` |
| Legacy: finished gauntlet run | `docs/gauntlet/<slug>/` with `report.md` present | → `.trash/<date>/gauntlet/` | → `backlog/gauntlet/` |
| Legacy: brief for a finished gauntlet run | `docs/specs/<slug>.md` (basename matches the run) | → `.trash/` | → `backlog/specs/` |

Work repos: crm-api, crm-web. Personal: notes-app.

## Fixed safety rules

- **`.playwright-mcp/auth.json` is never touched** — it's the saved SSO login state.
- A plan is "finished" per the drained-plan-dir row above. Anything ambiguous is left alone.
- `/tmp` is not touched — it self-cleans.
- The plan-dir, PRD and gauntlet rows sweep legacy artifacts only. New specs land in `docs/specs/`.
