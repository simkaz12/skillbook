# Flow-eval case format

`init` writes a case that has this shape:

```text
case/
  manifest.json
  public/
    ticket.md
    owner-answers.md
  profiles/
    baseline/{skills/,launch.json}
    candidate/{skills/,launch.json}
  private/
    expected.md
    quality-checklist.md
    variant-map.json
  control/
    runs.jsonl
  runs/
```

Put the ticket, relevant screenshots transcribed into prose, and the owner’s answers from grilling in `public/`. The same public tree goes to both variants; the runner records a digest of the whole tree and rejects a blind bundle when those digests differ. Keep expected findings and the checklist in `private/`. Do not place a solution, a baseline/candidate label, or a pricing estimate in `public/`.

Profiles are the actual variant under test. Copy the frozen skill files to `profiles/<variant>/skills/` and any changed hand definitions to `profiles/<variant>/agents/`. The runner copies both into `workspace/.claude/`. Put a real argv in `profiles/<variant>/launch.json` when the same adapter should launch every run:

```json
{"argv": ["/path/to/your-agent-wrapper", "--skills", "{skills}", "--input", "{public}", "--out", "{output}", "--session-inventory", "{inventory}"]}
```

An inline argv after `--` overrides this launch file for a one-off run. The utility passes `FLOW_EVAL_PUBLIC`, `FLOW_EVAL_SKILLS`, `FLOW_EVAL_OUTPUT`, `FLOW_EVAL_SESSION_INVENTORY`, and `FLOW_EVAL_PROFILE_SHA256` to the adapter. Have the adapter copy `FLOW_EVAL_PROFILE_SHA256` to `sessions.json.profile_sha256`; the cost report then says `attested`. This confirms only that the adapter echoed the selected profile digest. It does not prove that the model loaded those files.

Set `source.repository`, `source.revision`, and `source.snapshot_ref` to the pre-change repository state. For a code case, pass a clean checkout at that revision with `--source`; the utility checks its `HEAD`, then creates a fresh detached, depth-one local fetch in the neutral workspace. The fixture remains a git repository, so a runner or reviewer can use `git diff`, but it does not inherit the source checkout’s later objects or history. A non-git snapshot is allowed only when `source.snapshot_ref` names the immutable artifact used.

Each variant has its own `planned_phases`. This lets a five-hand baseline compete with a one-hand candidate. A session inventory reports what actually ran. The same coordinator can name several phases and counts once because it has one session id.

```json
{"sessions": [
  {"id": "coordinator", "phases": ["recon", "grill", "to-spec"], "usage": "main.jsonl"},
  {"id": "fe-trace", "phases": ["recon"], "usage": "fe.jsonl"},
  {"id": "runner", "phases": ["runner"], "usage": "runner.jsonl"}
]}
```

Pass `--session-inventory '{output}/sessions.json'`; the runner reads this file after the command exits. The adapter must list each main and child session and its JSONL. `--usage SESSION=PATH` remains available for a manual one-session run, but its phase coverage is unknown. A missing inventory, missing file, unreadable JSONL row, or usage row that lacks any token field makes totals `unknown`; it is never treated as zero. Usage rows must expose a message id plus Claude’s `input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, and `output_tokens`. This matches Claude Code assistant rows (`message.id` and `message.usage`). Repeated streaming rows for the same session and message id merge by taking the largest value of each field.

Put each frozen skill version under `profiles/baseline/skills/` or `profiles/candidate/skills/`. `launch.json` may hold the normal adapter argv, so `run` can launch it without an inline command. The runner expands `{workspace}`, `{public}`, `{skills}`, `{output}`, `{inventory}`, and `{source}`. It creates a new process group, kills that group at the timeout, and stores stdout, stderr, exit status, the profile digest, and reported sessions. It does not invoke a vendor SDK. A command can still read outside its workspace or start work the utility cannot account for; use a trusted wrapper that emits the inventory.

Pass `--artifact` once for each final report artifact. `review-pack` copies only those allowlisted files into `entry-01`, `entry-02`, and so on; it never copies stdout, stderr, transcript JSONL, or run metadata. The review bundle contains neither the variant map nor token totals. The case keeps the mapping privately until `cost-report` confirms that every entry has a completed quality record. The final cost report gives per-variant token fields and elapsed time separately. It does not invent prices or choose a winner.

For a pilot, start with two already-completed small tickets at pre-fix revisions. Run the current and candidate flows once each, review quality blind, then inspect the cost report. Change the candidate only after recording why quality was insufficient. Keep an untouched holdout case for the final check.

Offline smoke test:

```bash
python3 skills/flow-eval/flow_eval.py demo /tmp/flow-eval-demo
python3 -m unittest discover -s skills/flow-eval/tests
```
