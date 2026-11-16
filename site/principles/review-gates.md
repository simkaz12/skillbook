---
title: Review gates
covers: skill/verify-ticket, skill/preflight, skill/review-structure, skill/blast-radius, skill/debate, skill/how-to-test, skill/playwright, command/baseline, scripts/test-baseline.py, agent/spec-reviewer
---

Several checks sit between "the code is written" and "the pull request opens". Each one owns a different question, and the rules about what each may run keep them from repeating each other.

## Who checks what

- `spec-runner` runs each scope's Verify steps and nothing else. It reports whether the brief's own checks passed. It does not say whether the result is good enough to land.
- `spec-reviewer` is the gate. It runs the Codex adversarial review and rules on each finding: it holds, a locked bullet overrides it, it is ping-pong, it is a brief flaw, or it is refuted with the command and its output. It also checks each done scope against the brief and opens the running app to check behaviour a browser can reach. A Codex outage or a missing companion is reported as an unavailable gate and does not block.
- `verify-ticket` runs focused checks and drives only the acceptance criteria no reviewer observed live. The full suite is not its job.
- `preflight` drives the running app against four slips a green suite hides.
- `blast-radius` asks what a change breaks outside its own diff and proves the claim by running code.
- `review-structure` is an explorer, not a gate. Gates already existed, and the missing piece was code-quality exploration. A skill that tried to be both was rejected.
- `debate` puts a Claude seat and a Codex seat on the same subject for three rounds and folds the result into a ledger. It fixes nothing.
- `how-to-test` writes a manual test plan for a person and never drives the app.

## What each stage may run

The full suite runs once per ticket, in the background. `spec-reviewer` starts it on a final PASS and `land` awaits it. The run is diffed against a snapshot of already-failing test ids, keyed by the merge-base commit, built on first use and reused by every ticket on that base. Every other stage runs focused tests only. The reason is arithmetic: a ticket had about thirty full runs, most of them on an unchanged tree, and one work project's suite is red on its base. A plain full run says nothing about the ticket, so the diff against the snapshot is what carries the signal.

Rejected were every stage running the suite; a snapshot keyed by calendar date, because master moves during the day and the first verify of the day blocked on the run; starting the run on the runner's return, because a review FAIL would force a rerun; starting it at `land`, because `land` follows `verify-ticket` within a minute; and skipping the suite by changed path. The owner ruled on this on 2026-10-22.

In a split brief Codex runs once, in the review after integration. Codex reviews the working tree, so a per-lane gate would review sibling lanes' half-finished edits and raise findings about work that is not the lane's. Lane Verify steps are scope-local for the same reason.

## Who opens the browser

The reviewer owns the live-app check. Before that ruling the runner marked visual Verify items `needs-human` and moved on, so nothing between the grill and the reviewer ever opened the app. The owner declined to put browser work in the runner, and the reviewer already holds the brief and is the last gate.

## Codex findings

The reviewer, not the runner, disposes of every finding, and a refutation needs the command and output that justify it. A bare "refuted" stands as a required fix. After four rounds the loop stops and the open findings go to the owner. See [Delegation tiers](#/principle/delegation-tiers) for where the gate lives.
