<!-- Provenance: adapted from pstack (https://github.com/cursor/plugins/tree/main/pstack, MIT License, Copyright (c) 2026 Lauren Tan). See THIRD_PARTY_NOTICES.md. -->

# Judgment lens

Name the durable principle behind a specific incident — the thing that saves a future agent real time. Do not stop at the session's obvious learning; the useful principle is usually the one beneath it, including the one that complicates or contradicts the obvious reading.

Scan for:

- Mistakes made and corrections received
- User preferences and workflow patterns
- Codebase knowledge gained: architecture, gotchas, patterns
- Decisions and their rationale
- Friction in skill execution, orchestration, or delegation
- Repeated manual steps that could be automated or encoded
- Decisions that worked for the wrong reason, or survived only because the test path was lucky
- Verifications skipped, deferred, or self-reported instead of artifact-checked
- A local fix that missed the second-order effect — callers, sibling consumers, downstream state
- Architectural smells the immediate fix papers over
- Skills invoked too late or not at all, which is the canonical `tune description` case
- Implicit assumptions about scope, side effects, or what the user actually wanted

Evidence for this lens quotes what was said **and** names what wasn't — the check not run, the caller not opened, the skill not invoked.
