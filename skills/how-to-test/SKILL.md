---
name: how-to-test
description: Translates a just-completed change into a manual test plan for the human — reads the diff, maps each changed surface to the entry point that reaches it (route, screen, command, endpoint), and emits concrete go-here / do-this / expect-that / watch-this steps. Use after a task is done and matching `verify-ticket` evidence or preflight evidence with green suites passes, when the user asks "how do I test this", "what should I test", "where do I go to try it", or wants pointers to manually exercise new or fixed functionality; it writes steps for a person to run and never drives the app itself (that's preflight/playwright).
disable-model-invocation: true
---

# How to test

Translate the change you just shipped into a manual test plan a person can run — where to go, what to do, what to expect. Written for a human at a keyboard.

## Precondition
A completed change needs either current matching `verify-ticket` PASS, including its recorded caveats, or `preflight` PASS with green focused checks. Do not run preflight merely to duplicate valid verification evidence. If neither applies, say so — this skill assumes the change already works and only routes the human to see it.

## Build the plan from the diff, not memory
Read the real change first — `git diff <base>...HEAD --stat`, then the hunks. The plan covers what actually changed, not what you remember intending.

## Map each changed surface to its entry point
For every user-reachable change, name the door the human walks through:

| Changed thing | Entry point to give |
|---|---|
| FE page / route / component | the exact URL or nav path to reach it |
| Controller / endpoint | the UI action that triggers it (or a ready-to-paste curl if there's no UI) |
| Job / command / scheduler | the artisan/CLI command to fire it + where the effect shows |
| Config / infra / migration | the observable behaviour that changed + how to see it |

Pure internals with no user-visible surface: list them as **not user-testable** with the reason — don't send the human hunting for a screen that doesn't exist.

## Each item: go / do / expect / watch
- **go** — exact route, URL, screen, or command. Copy-pasteable.
- **do** — the interaction, with a concrete input (a real value, not "some data").
- **expect** — the observable success for the new/fixed behaviour.
- **watch** — the one neighbour most likely to have regressed, and where to glance to confirm it didn't.

Cover the happy path, one bad-input path if the change added validation, and the regression glance. Pointers, not prose.

## Output
```
## How to test — <branch>  (<base>...HEAD, N files)

### 1. <feature> — <route or command>
go:     /some/path
do:     <interaction with a concrete input>
expect: <observable success>
watch:  <neighbour> still <works>

### 2. ...

not user-testable: <files> — <why> (internal only)
```

## Guardrails
- Pointers for the human; never drive the app yourself.
- Ground every step in a changed file. If you can't trace a step to the diff, drop it.
- Don't restate the checks — green checks are the precondition, not a test step.
- Read-only on any tracker; never push or open a PR. The skill ends at the plan; the human runs it.
