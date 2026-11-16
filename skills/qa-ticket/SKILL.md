---
name: qa-ticket
description: Tests teammates' tickets as QA. Drives each ticket's acceptance from Jira against the running app, writes the evidence, then posts a short verdict comment and moves the ticket to In verification or Testing Failed. Use on "/qa-ticket PROJ-774 PROJ-777", "qa these tickets", or testing Testing-column tickets that are not the owner's; the owner's own work goes to verify-ticket.
allowed-tools: Bash(*/skill-project.sh *)
---

# QA ticket

The owner names one or more ticket keys. Main tests each one against the running app and leaves a verdict, an artifact and a Jira update per ticket. The work belongs to a teammate and is already merged, so there is no brief, reviewer result, fingerprint or `land` handoff. Proof follows the rules of `verify-ticket`'s "Prove the result" section; everything tied to the owner's own pipeline there (reviewer reuse, fingerprint, focused suites, baselines) does not apply.

## Take the tickets

Read each ticket with its comments. A ticket assigned to the owner is not QA: say so, point at `verify-ticket`, and skip it.

Acceptance comes from the description, then the comments. A later comment from the reporter or product (feedback, a narrowed ask) wins over the description where they conflict. Write the criteria as a numbered list in the artifact before testing. A criterion that cannot be stated without guessing the intent is `BLOCKED` with the question it needs.

Find the change from the PR links on the ticket, `gh pr view <n>`, and `git log --grep <KEY>` in each repo. Then run `bash ~/.claude/skills/../scripts/pull-base.sh --backup-dir docs/qa/<YYYY-MM-DD> --key <KEY>` in each repo the ticket touches, and check that every change commit is in HEAD. A commit still missing after the pull makes the ticket `BLOCKED` with the repo and commit named. A pull that exits 3 or 4 blocks the ticket with the script's report. Never stash.

## Test

Dispatch one `hand-ex` per batch of tickets. Batches run one after another, because they share the browser. Hand it the project's launch, authentication, feature and driver instructions from Project additions, the numbered criteria, and the change commits. The hand:

- drives the real surface for each criterion
- proves the active identity before trusting a permission result
- seeds missing data through the project's factories and lists the rows it left
- runs queued work on an isolated queue
- takes one screenshot per ticket with a visible surface

It returns evidence as text, and main writes the artifact. No test suites run here, because QA observes behaviour.

## Verdict

- `PASS`: every criterion was observed working.
- `FAIL`: a criterion was observed broken. Name the route or record, the data, and what does not happen.
- `BLOCKED`: a criterion could not be observed (missing credentials, an external service, unclear intent, a commit on no fetched ref).

A defect outside the ticket's criteria goes in the artifact as a side note. It does not make the ticket fail.

The artifact goes at the project's QA location. It holds the criteria, the change commits, each repo's revision, the identity used, the evidence per criterion, the seeded rows, the screenshots, and the verdict.

## Jira

Jira writes happen only after the artifact exists. The comment list, mentions and the transition call are in Project additions.

- `PASS`: post one line from the pass list exactly as written, then move the ticket to `In verification`. No owner check.
- `FAIL`: draft one comment in the fail shape and show it to the owner with the ticket key. Post it only after the owner says ok, then move the ticket to `Testing Failed`.
- `BLOCKED`: no comment and no move. Report what the observation needs.

Anything else, such as a pass with a side note, goes to the owner as a draft first. The tool cannot edit or delete a comment, so a bad one stays until the owner removes it by hand.

Report one line per ticket: key, verdict, comment id, new status, artifact path. Close the browser tabs and processes this run started.

## Project additions

!`$HOME/.claude/skills/../scripts/skill-project.sh qa-ticket`

If the line above shows a raw command instead of content, run it.
