<!-- Provenance: derived from Matt Pocock's `skills/engineering/domain-modeling/GLOSSARY-FORMAT.md` (https://github.com/mattpocock/skills, MIT License). See THIRD_PARTY_NOTICES.md. -->

# CONTEXT.md format

`CONTEXT.md` is the project domain glossary. It captures the language of this project's business domain — the terms that mean something specific *here* and that team and code disagree about when left undefined. It is not the generic architecture vocabulary (module / seam / depth); that lives in `~/.claude/LANGUAGE.md`.

## Structure

```md
# {Project / context name}

{One or two sentences: what this context is and why it exists.}

## Language

**Prospect**:
{One or two sentence definition of the term.}
_Avoid_: Lead, opportunity

**Sales Account**:
A client organisation that places projects and quotes.
_Avoid_: Client, customer, account

**Commission Rate**:
The percentage a salesperson earns on a project, versioned and retire-able.
_Avoid_: Rate, fee, percentage
```

## Rules

- **Be opinionated.** When several words name the same concept, pick the best and list the rest under `_Avoid_`.
- **Keep definitions tight.** One or two sentences. Define what it IS, not what it does.
- **Domain terms only.** General programming concepts (timeouts, transformers, validators, queues) don't belong even though the codebase uses them everywhere. Before adding a term, ask: is this unique to this project's domain, or a general programming concept? Only the former belongs.
- **Group under subheadings** when natural clusters emerge (e.g. Sales, Commissions, Projects). A flat list is fine if the terms form one cohesive area.

## Single vs multi-context

Most repos are single-context: one `CONTEXT.md` at the root.

If the domain ever splits hard enough to warrant separate glossaries per module (`src/Commissions/`, `src/Prospects/`, …), promote to a multi-context layout: a `CONTEXT-MAP.md` at the root lists each context, where its `CONTEXT.md` lives, and how they relate.

```md
# Context Map

## Contexts

- [Sales](./src/Prospects/CONTEXT.md) — tracks prospects through to won Sales Accounts
- [Commissions](./src/Commissions/CONTEXT.md) — rates, splits, and payouts

## Relationships

- **Sales → Commissions**: a won Prospect's project feeds Commission Rate calculation
- **Sales ↔ Commissions**: shared reference to the salesperson (User) by id
```

Inference order: if `CONTEXT-MAP.md` exists, read it to find contexts; else if a root `CONTEXT.md` exists, single context; else create a root `CONTEXT.md` lazily when the first term resolves. When multiple contexts exist and the topic's context is unclear, ask.
