---
name: verify-ticket
description: Checks an implemented ticket, brief, or delivered named change against its acceptance criteria, with focused regression checks, leaving an evidence-backed verdict. Use for verify this ticket, verify this brief, verify delivered change, or when flow reaches completion; do not use to review unimplemented design prose, write a manual test plan, build a generic project verification map, or QA a teammate's ticket (that is qa-ticket).
allowed-tools: Bash(*/skill-project.sh *), Bash(*/test-baseline.py *)
---

# Verify ticket

Main owns one verdict and durable artifact. Dispatch one bounded `hand-ex` to exercise the acceptance criteria no earlier stage observed live; it returns evidence as text for main to write or update. A criterion the reviewer's `### E2E` section observed live on the current fingerprint is already proven: cite it and reuse the rows it lists. The hand drives only the criteria no reviewer observed, plus any whose proof predates the current fingerprint. When none remain, dispatch no hand. The runner's own live output is not reused; that is the implementer checking its own work. Reuse the recon, grill agreement, brief, reviewer result, named diff, and relevant evidence already available. Browser work uses the shared instance sequentially, with no builder changing the tested surface during the check.

An unimplemented brief has no result to verify. State that missing implementation, retain the current authorization, and stop; do not build it. The failure check under `Bug or bounce` is the exception: it runs before the fix exists.

## Establish scope

Start from the latest base: run `bash ~/.claude/skills/../scripts/pull-base.sh --no-switch` in the repo first (and in its partner when the ticket spans both). Inside `flow`, skip the pull: flow already pulled at its start, and a second pull would move the base under work the reviewer already passed and change the merge-base the test snapshot is keyed on. The revision recorded in the artifact is the HEAD after the pull, or the current HEAD when the pull was skipped. Record the tested revision, product-code/config/test-input fingerprint, environment, intended identity, exact diff or paths, the brief's acceptance criteria and `Decisions locked`, and evidence already known. Also record the exact command that produced the fingerprint (for example `git diff <rev> -- <Files> | sha256sum`), so `land` can recompute it the same way. Exclude report, log, and screenshot churn from the fingerprint. Reuse a log only when its revision, fingerprint, environment, command, coverage, and exit status match. Before the verdict, check `git status` and the diff stat against the proof. If no product file changed, say so in one line and give the verdict; do not rebuild or recompute. If one changed, rerun only the proof for the changed paths.

Give the hand the project's actual launch, authentication, feature, and driver instructions. Do not infer a browser, command, or credentials from another project. When authentication matters, prove the active identity and compare it with the intended one.

## Bug or bounce

When the work fixes a bug, or a ticket the tester sent back, prove the failure before anyone fixes it. Dispatch the hand to replay the reported steps on the unfixed code, under the identity the reporter used, and capture the actual fault: the wrong screen state, the request and its status, the console error. Write it to the artifact as a dated `Failure evidence` section with the claim quoted verbatim, the steps, and what was observed. This check runs before a fix exists; it writes the evidence and gives no verdict.

Each claim ends as `reproduced`, `not reproduced`, or `differs` (the fault is real but is not what the report says). Only a `reproduced` claim goes to a fix. The other two stop the work and go to the owner with what was tried; never fix from the report's words alone.

After the fix, replay the same steps. `PASS` needs the fault gone on those steps, plus the criteria below. A fix with no `Failure evidence` behind it is `BLOCKED`.

## Prove the result

Exercise the real surface appropriate to the project: browser, endpoint, CLI/TUI, generated artifact, job, or another documented entry point. Observe the result establishing each applicable criterion. Suites alone are not runtime proof. Visual comparison is required only for a visual criterion. Missing local data and queued work are setup, not limits on observation. Seed through the project's factories, leaving the rows in place and listing them in the artifact. Run a queued job on an isolated queue and read the artifact it writes. A consumer that the brief or recon claims inherits the change is an applicable criterion. When the deliverable is a surface the owner will use directly, include one screenshot in the verdict message.

The full suite is never run here. Where the repo's `testing.md` section has a `full:` line, it runs once per ticket, in the background, started by `spec-reviewer` on PASS and awaited by `land`; the CRM scope has none (owner ruling, 2026-11-03). Run the scope's `focused:` commands over the changed test files and the tests of the changed paths' direct callers, reusing a matching runner or reviewer run. A focused failure is re-run once; a pass is flaky and does not block. A repeat failure is `introduced regression` unless `python3 "$HOME/.claude/skills/../scripts/test-baseline.py" status .` reports `snapshot present` and `~/.cache/test-baseline/<repo>/baselines/<merge-base>.json` records that test id as `fail`, in which case it is `pre-existing failure`. Never build a snapshot here. A repo with no `testing.md` runs the same focused checks from its docs, and the report notes "no snapshot configured".

Reuse one existing verification/QA artifact or the brief's evidence section. If neither exists, write `docs/verification/<slug>.md` with scope, provenance, identity, criterion evidence, regression results, red classifications, and verdict. Project additions can define a different durable location. No product changes, tracker writes, commits, pushes, or merges happen here. A proven defect routes to the existing authorized implementation work, then only its affected proof is rerun. After evidence persists, close only browser tabs and processes this verification started.

## Verdict

Classify every red result as `ticket defect`, `introduced regression`, `pre-existing failure`, `broken fixture`, or `observation blocked-or-unproven`. A pre-existing failure needs the merge-base snapshot or equivalent evidence.

`PASS` requires all applicable acceptance criteria observed and required regression evidence. `FAIL` names a proven defect or introduced regression. `BLOCKED` means required proof is unavailable, an observation is unproven, or a red result is unclassified. A material contradiction with the brief's `Decisions locked` is a specific gap, never a silent redesign. Caveat known unrelated reds on a PASS. A caveat the tester would hit on first use is a predicted bounce, not a note; the verdict names it as a gap and routes it back to the authorized work, even when the brief fenced that surface off. An applicable criterion left unobserved is not a caveat; it makes the verdict `BLOCKED`.

Each criterion row in the artifact carries a `Conditions` value. `reporter` means the effect was seen under conditions that match the reporter's on every axis the criterion depends on: identity, the real external service, viewport and data shape. The local stack counts when those match. `local-real` means the real code path ran but one of those axes differs. `seeded` means the path ran on factory or injected data. `stub` means a faked response or dependency. Observe the effect, not its record: a saved pivot row does not observe a notification, and a stubbed response does not observe a third-party success. For a bug reported with a screenshot, derive the reporter's CSS width from page geometry, never from image pixels, and write the derivation in the row. A row other than `reporter` needs an owner waiver in the artifact that names the predicted bounce; without one the verdict is `BLOCKED`. A waived pass reads `PASS (waived: <criterion ids>)`.

A direct verification request starts here from current evidence, without `to-spec` or a runner.

## Project additions

!`$HOME/.claude/skills/../scripts/skill-project.sh verify-ticket`

If the line above shows a raw command instead of content, run it.
