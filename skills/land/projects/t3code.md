### t3code

| Branch | Subject | Ends at | Reviewer |
|---|---|---|---|
| cut from `dev`, named after the work, lowercase words joined with dashes, no type prefix (`city-backgrounds`, `run-selection-in-terminal`, never `feat/…`) | upstream's conventional commit in plain language, `type(scope): description`, lowercase (`fix(web): new threads no longer spike CPU`) | PR into `dev` on `origin` (`<owner>/t3code`) | none |

`origin` is the public fork; `upstream` is `pingdotgg/t3code` with its push URL `DISABLED`. Never push or open a PR anywhere but `origin`. `origin/HEAD` is `main`, which only mirrors upstream and is never a PR base here; the fork builds from `dev`.

**Proof path.** AGENTS.md forbids plans and notes in the worktree, so `to-spec` and `verify-ticket` write to `~/.claude/specs/YYYY-MM-DD-<slug>.md`; the proof is that brief's `## Verification` section with its revision, fingerprint and the command that produced it. An empty `docs/verification/` is not a missing proof.

**Opening the PR.** `gh` resolves this fork's parent as the default repo, so a bare `gh pr create --base dev` fails with "No commits between dev and <branch> … Head ref must be a branch". Always pass `--repo <owner>/t3code --base dev --head <branch>`.

**Live hooks.** `core.hooksPath` is `.vite-hooks/_`; `pre-commit` runs `vp staged` (vite-plus lint and format over the staged files). A failure there stops the commit, as always.

**Validation before landing.** No `testing.md` section, so the report says `suite    none configured`. The gate is the verify-ticket proof plus the focused tests and per-package typecheck the reviewer already ran; never `vp check` or `vp run -r …`.

**PR body.** Two or three lines: the shape of the change, the brief path, and upstream's closing line naming the model and harness that did the work (AGENTS.md "Pull requests"). No headings, no file inventory.

**After the PR.** No post-PR step. Rebuilding the installed fork from `dev` is the owner's step, per `CLAUDE.local.md`. Back to `dev` with `git switch dev && git pull --ff-only`.
