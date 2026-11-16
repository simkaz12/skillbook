---
name: flow-eval
description: Run a bounded, blinded comparison of two agent-flow or skill versions on frozen cases, then report quality before token use. Use when someone asks to compare or evaluate a recon, grill-me, to-spec, runner/reviewer flow, or a proposed skill change.
---

# Flow eval

Use this only when a workflow change needs evidence. It runs no model by default.

Create a frozen case before either variant runs. `public/` holds the ticket and the owner’s fixed grill answers. `profiles/<variant>/skills/` holds that variant’s frozen skill files; the runner copies them to the neutral workspace’s `.claude/skills/`. `private/` holds expected answers, the quality checklist, and the baseline/candidate map. A candidate receives a fresh copy of `public/`, its profile, and, when supplied, a copy of the source snapshot. It never receives `private/`.

```bash
python3 skills/flow-eval/flow_eval.py init /tmp/recon-pilot/PROJ-123
python3 skills/flow-eval/flow_eval.py run /tmp/recon-pilot/PROJ-123 \
  --variant baseline --out /tmp/recon-pilot/runs/one \
  --source /path/to/pre-change-checkout --session-inventory '{output}/sessions.json' \
  --artifact '{output}/final-report.md' \
  -- /path/to/your-agent-wrapper --skills '{skills}' --input '{public}' \
    --out '{output}' --session-inventory '{inventory}'
python3 skills/flow-eval/flow_eval.py review-pack /tmp/recon-pilot/PROJ-123 \
  --run /tmp/recon-pilot/runs/one --run /tmp/recon-pilot/runs/two --out /tmp/recon-pilot/review
```

Give the human reviewer only `review/`. They complete `quality-template.json` without knowing which entry is which. Then create the cost report:

```bash
python3 skills/flow-eval/flow_eval.py cost-report /tmp/recon-pilot/PROJ-123 \
  --review /tmp/recon-pilot/review --quality /tmp/recon-pilot/review/quality.json \
  --out /tmp/recon-pilot/cost.json
```

Read [the case format](references/case-format.md) before preparing a real pilot. The utility enforces run caps, timeout, non-overwrite, identical model/environment metadata, private-input exclusion from its workspace, and complete reported usage. It cannot sandbox a command, discover a child a wrapper fails to report, or prove that a supplied checkout predates the fix; the operator must supply a clean checkout at the manifest revision and an adapter that writes the session inventory.
