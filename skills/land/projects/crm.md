### CRM

Applies to crm-api and crm-web.

**Proof path.** `verify-ticket` writes `docs/qa/<YYYY-MM-DD>/PROJ-<n>.md` here, and that is the durable record. An empty `docs/verification/` is not a missing proof.

**Proof fields.** Before the first commit, read the ticket with `jira_tool get`, comments included. Refuse when the proof has no `Jira read through` line or no `## Tester comment` section, and name what is missing. A comment newer than `Jira read through` from anyone but the owner stops the land: quote it to the owner, who decides whether the piece reopens.

**Branch, subject, base.** Branch `PROJ-xxx/<ticket title>`, subject `PROJ-xxx/<ticket title>`, PR into `dev`, one named reviewer. The subject is the branch name with the dashes back as spaces, with the ticket title verbatim from Jira. Do not paraphrase the title.

**Quick fix.** A quick fix is never landed (see flow): no branch, no commit, no PR, no Jira. If asked to land one, say so and stop.

**No body, ever.** Not on the commit, not on the PR. Pass `--body ""`. Anything worth explaining goes in the QA artifact.

**Post-PR step: Jira.** Once every PR in the run is open and its reviewer is confirmed, update the ticket with the Jira MCP write tool.

1. Read the ticket with `jira_tool get`, comments included. A PR link already on the ticket does not get posted again.
2. Transition it to `In Code Review`, once per ticket rather than once per repo. If the tool refuses, put the refusal in the report and skip the transition.
3. Post the proof's `## Tester comment` text as written, as its own comment before the PR comment.
4. Post ONE comment for the whole run: one line per repo with the repo label and the link, in `[label](url)` form, because the tool only builds a Jira link from that shape. The tool cannot edit or delete a comment, so check the body before sending.

A fix pushed to a PR that is already open gets no comment and no transition. A new PR for the same ticket gets both.

**Report.** Add a `jira` line after `pr` with the transition and the comment id.
