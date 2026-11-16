---
name: fixture-dangling
description: Fixture skill naming a skill that does not exist.
---

# fixture-dangling

Run the `never-existed` skill first.
Write it through `also-missing`.
Run the `article-missing` pass afterwards.
Run `jq` over the file and use `python3` for the test.
Grounding arrives via the `SubagentStart` hook.
Read it with the `Read` tool and dispatch a `fixture-agent`.
