---
name: blast-radius
description: Finds what a change could break outside its own diff, then proves the one fact it is safe because of by running real code instead of writing it up. Use for "blast radius of X", "what could this break", "is this safe to ship", or reviewing a small diff you don't trust yet.
---

> Provenance: derived from `pstack/skills/blast-radius` in https://github.com/cursor/plugins/tree/main/pstack (MIT License, Copyright (c) 2026 Lauren Tan), edited by the repo owner. See THIRD_PARTY_NOTICES.md.

# Blast radius

Find what a change breaks somewhere else, before it ships.

Listing the callers is not the job. The agent can grep those in a second. The job is the breakage grep won't show you.

## Don't trust your own writeup

A blast-radius writeup that sounds right is worthless — it reads as convincing whether or not it's true. Don't hand back the writeup. Find the one or two facts the whole thing depends on and prove them by running code.

### How sure are you

For each fact the change's safety depends on, get it as far down this list as is cheap, and say where it stopped.

1. You said so. Worthless on its own.
2. You pointed at the line. A real `file:line`, or the library's own source.
3. You showed the bad case can't happen. You walked the failure step by step and it doesn't reach.
4. You ran it. A script or test that calls the real code and fails loud if you're wrong.
5. You reproduced it in the running app.

Any safety fact you can't get to step 4, say so out loud. Don't write it up as settled. Step 4 is usually one small test or `tinker` snippet calling the exact function you're worried about, run the way the repo's CLAUDE.md says to run things.

## Steps

1. **Read the change.** `git diff`, the symbols it adds, changes and deletes, and what it now does differently — including the part the diff doesn't spell out. `git log` / `gh pr diff` for the commits behind it.
2. **Find the one fact it's safe because of.** Most changes that look scary are safe because of a single fact, like "this call only drops already-dead cache entries and does nothing else". If it holds, most of the scary cases die at once. Spend your time here, not on a long list of maybes.
3. **Look where grep stops.** `Grep` the symbol across the repo for call sites outside its own definition — that's the cheap half and it's now done; too many to enumerate is `unresolvable — foundational`, not a guessed count. The rest are the callers grep doesn't see:
   - **Dynamic names.** Eloquent accessors (`full_name` → `getFullNameAttribute`), `$model->{$field}`, `config()`/`app()` string keys, route and Blade view names, `$fillable`/`$casts` entries. A rename greps clean and still breaks.
   - **Jobs already queued.** In-flight payloads were serialized against the old class — changed constructor, renamed job, dropped property. `SerializesModels` re-fetches the row at run time, so a renamed or deleted column bites the consumer, not the dispatcher.
   - **Observers and model events.** `save()` fires them; a query-builder `update()`/`delete()` and `saveQuietly()` do not. Moving a write between the two silently adds or drops every observer.
   - **Transactions.** An event or job dispatched inside `DB::transaction` fires before commit unless it's `afterCommit` — the consumer reads a row that isn't there yet. Read what's nested in the transaction, not just what the diff touches.
   - **Cache.** Values serialized by the old code outlive the deploy, and a key built in two places drifts. Both break on read, not on write.
   - **Payload shape.** `JsonResource`, transformers, Python serializers — the wire is an interface with no in-language caller. Renaming a field changes the contract without touching a call site.
   - **Nova.** Resources, filters, actions and policies read the model directly, so a changed scope, accessor or cast lands in the admin UI with no app-side caller.
   - **The other repo.** The caller often lives across the pair — `crm-api↔crm-web`. Grep the partner too, and remember a shipped client build does not redeploy with the backend.
   - **Downstream of the bytes.** A DB column, another language reading the same rows or JSON, a feature flag, code three hops away, a pinned dependency version and any local patch to it.
4. **Be honest about each risk.** Give it a real chance of happening and a real cost if it does. Keep the risks you confirmed; list the ones you checked and cleared separately. Cite a real `file:line`, a search that finds nothing is still an answer, and never invent a caller or an API.
5. **Prove the one fact.** Write the test or snippet that runs the real code, run it, and paste what happened. If you can't prove it cheaply, mark it unproven. Don't round up.
6. **Wide change.** Fan out parallel `hand-ex` explorers, one per surface (queue, cache, Nova, FE contract) — one agent can't hold them all. Cross-model challenge is not this skill's job; the fix ships through `hand-do`, and `spec-reviewer` runs the codex review on the working tree.

## What to hand back

- **What it does.** What changed, including the part that isn't obvious.
- **The one fact it's safe because of.** State it, and hand back the proof from step 5.
- **Risks.** Only the real ones. Each names how it breaks, the `file:line`, how likely and how bad, and how to check. Paste the proof for the ones that matter.
- **Cleared.** What you checked and why it's fine.
- **Before you merge.** The cheapest test or repro that catches the real bug, including the script you wrote.

**Reply:** the writeup above, with the one safety fact either proven or marked unproven.
