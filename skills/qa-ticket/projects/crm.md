**QA location.** `docs/qa/<YYYY-MM-DD>/PROJ-<n>.md` in the repo that carries the change.

**Launch and authentication.** Use the `playwright` skill's project files for crm-api and crm-web, and the credentials file `.claude/PW_CREDS.md`.

**Jira.** Post and transition with the Jira MCP write tool (`jira_write_tool`), passing either repo name as `project`.

- Pass comment: one line from a fixed list of short pass phrases, posted as written.
- Fail comment: the failing criterion, the route or record, the data, and what does not happen. Show it to the owner before posting.
- Move passing tickets to `In verification` and failing ones to `Testing Failed`.
