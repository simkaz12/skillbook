### skillbook

| Branch | Subject | Ends at | Reviewer |
|---|---|---|---|
| derived from the work | bare lowercase, one or two words | PR into `master` | none |

Live hook: `corpus-check.py`.

**Mechanical proof.** Skills and config have no drivable surface for `verify-ticket` to exercise, so work here will never carry a proof. Prove the artifact mechanically instead, before committing:

- every touched `SKILL.md` has frontmatter that parses as YAML and carries `name` and `description`
- a skill's `name` matches its directory
- every touched shell script passes `bash -n`


**Land from a worktree; the live checkout never moves.** `~/.claude/skills` points into this working tree, so whatever is on disk here is the config every session runs. Switching it to a PR branch and back to `master` puts the pre-PR files on disk until the merge, and the landed change stays out of use until someone pulls. Instead:

1. `git worktree add --no-track /tmp/land/skillbook-<branch> -b <branch> origin/master`. Without `--no-track` the branch tracks `origin/master`, so a plain `git push` refuses on the name mismatch.
2. Bring over only the selected change, by copy or by patch. Files here often carry other uncommitted work, so never copy a whole file unless all of its diff is in the selection.
3. Run the mechanical proof, commit, push and open the PR from the worktree, then run `git worktree remove` on it.

This replaces the generic switch-back step: the live checkout stayed on `master` throughout. Once the PR merges, `bash ~/.claude/skills/../scripts/pull-base.sh` here makes the change live from git. The script backs up and reapplies overlapping uncommitted edits itself; on exit 3 or 4, report its output rather than stashing.
