---
name: recon
description: Progressively map one Jira ticket before design, starting with targeted orientation and expanding only for named evidence gaps. Use when the owner says recon <ticket> or wants the change surface understood before a grill; read-only, never edits code or changes Jira.
---

# Recon

Recon establishes facts for the next decision. It does not propose approaches or write fixes. A small ticket does not earn a fleet.

## Args

- `recon <n>` / `recon PROJ-<n>` → `TICKET_ID=PROJ-<n>`.
- Anything else → error and STOP.

## 1 — Orient

- Fetch the ticket with comments and attachments. Transcribe every image attachment before any handoff.
- Brief the owner before any trace. The owner has not opened the ticket. Print in the conversation, in the ticket's own words: the issue (what a user sees today, and where in the app by its own labels), the ask (what should happen instead), who asked and the reason they gave, what the comments added or changed since the description, what each attachment shows, and one line for any term the ticket assumes (a report name, a role, a status). Quote the operative sentence. When a phrase has two readings, quote it as written and choose neither; it goes under Uncertainty. No file paths or symbols here; those come after the trace. Where the ticket is silent on a point (no reason given, no expected result), write "the ticket does not say" and leave it unfilled. Do not wait for a reply; carry on with Orient.
- Start from the latest base: run `bash ~/.claude/skills/../scripts/pull-base.sh --no-switch` in the repo first (and in its partner when the ticket spans both).
- Recall with `memory_recall` on the scope that `hooks/scope-map.sh` resolves for the repo, passing `audience: "navigator"`, and query relevant decisions. Then recall again with `kind: "defect"` for each area the ticket touches, so bugs seen and left there surface before the work starts; each one that bears on the ticket becomes a fold-in candidate in the report. Check linked PRs and ticket-key history only when the ticket or recalled context points there.
- State the acceptance criteria, candidate surface, and the facts still needed to explain the change. Label each claim `[ran]`, `[read]`, `[recalled]`, or `[unknown]`.

If a material fact remains unknown, choose **at most one** initial bounded trace for the most important gap: the named BE or FE surface, a history question, or live behavior. A bug starts with reproduction of the outcome its acceptance needs, not of the first error the reporter hit; that error hides every layer behind it. For a value that must save, write it, reload, and read the stored row, once per state change the requirement implies: unset to set, set to changed, set to cleared. Give the explorer one question, paths or symbols if known, the ticket text, and the same evidence labels. If existing evidence is sufficient, reuse it and move to the next activity without dispatching.

## 2 — Expand only for evidence gaps

After the initial result, list the remaining evidence gaps by question. Expand only when an answer is necessary to state the behavior, affected surface, contract, or test path.

- Trace the paired repository when the first trace names a cross-repo contract or leaves layer unclear.
- Inspect history when a prior decision, regression, or linked change could alter the requirement.
- Observe the running app when current behavior, available data, or the actual wire contract is a fact the brief needs.
- Search sibling tickets only when duplication, scope conflict, or an incomplete target list is a concrete concern. A ticket held after a failed retest, or a surface name that matches no string in the code, is such a concern: run a Jira text search on the surface's UI label.
- When a defect class shows on one surface, check that class on every surface the ticket changed and on every other consumer of the changed module (exports, sibling lists, jobs), with a round trip per surface. Define the class by the rule that broke, not by the first symptom, and trace what each consumer sends rather than which function it calls. A shared error string, guard, or handler in one layer says nothing about the layer in front of it or behind it.
- When the change creates or alters a state (a flag, a date, a linked record) or fires an event, trace every consumer of that state and every side effect of that event (notifications, mail, activity log, queued jobs, outbound integrations), on every write path that reaches it: create, edit, delete. A form field that names recipients or targets is traced to delivery on each of those paths. Name each consumer under `What it touches` as a surface the brief must cover or ask about. A consumer left unnamed is where the tester goes next.
- When the change gives a message to an outcome that used to be silent (a not-found, an empty result, a skipped send), list every code path that produces that outcome. Each one gets its own message, or the report names the paths that share one.

Each added hand gets one bounded question and returns evidence labels, source paths and revision where available, and unanswered questions. Mechanical one-hop answers go to `bolt`. Stop when the next step can state the work without pretending an unknown is settled.

## 3 — Reconcile → report + handoff

Write `docs/recon/PROJ-<n>.md`, then print a tight summary that opens with the issue and the ask in two sentences. This existing report is the durable handoff only when the conversation resets or another worker needs it; do not maintain a second status document.

### Report — `docs/recon/PROJ-<n>.md`

```
## PROJ-<n> — <title>
Layer: BE | FE | BE+FE | unknown   ·   Type: feature | bug

### The ask
Issue: <what a user sees today, and where in the app>
Ask: <the requester's stated intent, in the ticket's words>
Asked by: <reporter> — <the reason given, or "the ticket does not say">
Ticket says: "<operative sentence, verbatim>"
Comments and attachments: <what each adds or changes, or none>

### What it is
<acceptance criteria and observable behavior>

### Evidence
- <claim> — <path or runtime check> @ <revision if known> [ran|read|recalled]

### What it touches
- <path>:<symbol or area> — <role in the flow>

Fold-in candidates:
- <record id> — <where> — <symptom> — left because <reason> — status <open|taken by thread>
(or `none`)

### Current behavior
<observed behavior, or why it remains unknown>

### Constraints and prior context
<relevant decisions, linked changes, and their evidence>

### Uncertainty
- <question> [missing fact | product decision] — <what would settle it>

### Testability
- <criterion> — predicted Conditions `reporter | local-real | seeded | stub` — <why; seeding or access it needs>

next: grill-me | diagnose | to-spec — blocked on: <unresolved product decisions and unanswered code or data gaps, or none>
```

The predicted Conditions use `verify-ticket`'s values, so the grill sees every waiver the proof will need before work starts. A criterion predicted below `reporter` also goes under Uncertainty as `[missing fact]`, with what would settle it: a key, a known-good record, a staging run. An external service the sandbox cannot reach always lands there; Testability alone never holds it.

Reconcile conflicting findings; never promote an assumption. A non-derivable product decision blocks dependent implementation and goes to `grill-me`. Before an Uncertainty item carries `[product decision]` or names a person to ask, try to derive it. Read the commit and ticket that introduced the behaviour, search sibling tickets on the surface's label, and check the loaded grounding. Only what survives those checks is non-derivable. A ticket phrase with two readings ("skip the prospect/call process" on PROJ-791) is an Uncertainty item marked `[product decision]`; recon never picks a reading, and a brief never locks one. A code or data question stays a recon gap until it is answered. Bugs are not ready for a fix until the outcome has been reproduced or the report says why reproduction was impossible. A code path that reads as deterministic is a reason to skip, not an impossibility.

## Guardrails

- One ticket per invocation. Read-only: recon and its explorers never edit code. Never transition or comment on the Jira ticket.
- Evidence outranks confidence: `[ran]` beats `[read]`, which beats `[recalled]`.
- A claim names the layer it was read at. A validator that accepts a value does not show the value is stored. "No change needed in X" must be `[ran]` before it enters a report or brief.
- Do not make layer, scope, or a prior verdict proof. Recheck inherited evidence when its revision conflicts with the current surface or a material gap appears.
