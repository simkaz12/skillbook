# Load context (on demand)

Fetch what's missing; skip what's already in context.

## 1. Scope from cwd

Use the `Tabularium scope` column in `Projects/CLAUDE.md` — it is the only copy of that mapping.

No match → ask. An unregistered scope is a hard error, never auto-created.

## 2. Vocabulary

`Read ~/.claude/LANGUAGE.md`.

## 3. Project memory

Nothing loads at session start. Recall on demand with `mcp__tabularium-mcp__recall(query=..., scope=<scope>)`; prior decisions via `mcp__tabularium-mcp__decisions_query(query=..., scope=<scope>)`.
