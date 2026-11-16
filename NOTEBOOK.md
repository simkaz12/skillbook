# Notebooks

Transient notes that don't warrant Tabularium weight. **Skills don't auto-append** — the user explicitly says "save to notebook" and the assistant appends.

## Locations

- **Per-project:** `~/.claude/projects/<encoded>/notebook.md` — alongside `MEMORY.md`. Grill recommendations, blockers, project-specific observations.
- **User-scope:** `~/.claude/notebook.md` — skills, agents, hooks, cross-project tooling notes.

`<encoded>` mirrors the harness project key: `/home/user/Projects/crm-api` → `-home-user-Projects-crm-api`.

## When to use notebook vs Tabularium

| Notebook | Tabularium |
|---|---|
| Maybe useful later, won't re-trigger workflows | Must surface in future sessions |
| Manual browse (grep, scroll) | Vector search, hot-load |
| Cheap append | Adds to Tabularium weight |
| Grill recommendations, blockers, deferred ideas | Decisions, conventions, feedback rules |

## Format

Newest on top. Append:

```
## YYYY-MM-DD HH:MM — <source>

<content>

---
```

`<source>` = skill name (e.g. `/improve`), agent name, or `manual`.
