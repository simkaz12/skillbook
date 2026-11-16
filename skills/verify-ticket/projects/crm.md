Reuse the ticket's recon, agreement, brief, reviewer result, and existing QA artifact. The existing dated `docs/qa/<date>/` artifact remains the durable record; create `docs/qa/<YYYY-MM-DD>/PROJ-<n>.md` only when none exists.

Pass the hand the exact `.claude/PW_CREDS.md`, the relevant `.claude/features/<feature>.md`, and `~/.claude/skills/playwright/SKILL.md`. Drive the real acceptance path sequentially. Check the authenticated identity with the documented identity recipe. Permission work proves both allowed and denied cases through real requests under that identity.

A ticket in Testing Failed: the claim is the tester's Jira comment and its screenshots. Read it through the Jira MCP (`jira_tool` action `get`, `include_comments: true`) and quote it verbatim, together with every other comment posted since the last land. Reproduce on the local app at `dev`, before any fix branch exists. The `Failure evidence` section goes in the artifact.

Every artifact carries two fields that `land` checks:
- `Jira read through: <comment id>`, the newest comment on the ticket when the verdict was written.
- `## Tester comment`, the text `land` posts to Jira as written, followed by a `Covers: <criterion ids>` line that is not posted.

Staging is the reporter's environment. Replay a Testing Failed claim there as well as locally, since that is where the tester saw it. Writes on staging stay to what the criterion needs, and the artifact lists every row created.

Run or reuse the owning repository's checks. A change across both repositories needs evidence for both. Keep command output, screenshots, and other durable proof with the ticket artifact; close browser tabs and processes started for the check.

A quick fix writes `docs/qa/<date>/quick-<slug>.md`.
