# Language

> Attribution: the vocabulary and principles in this file derive from Matt Pocock's skills (https://github.com/mattpocock/skills, MIT License, Copyright (c) 2026 Matt Pocock). The examples and surrounding edits are the repo owner's. See THIRD_PARTY_NOTICES.md.

Shared architecture vocabulary. Use these terms exactly in any skill, plan, review, diagnosis, or design discussion — don't substitute "component," "service," "API," or "boundary." Consistent language is the whole point: the words index the concepts, and the concepts index each other.

**When to load.** Read this file at the start of any skill that proposes architecture (improve, simplify, review, diagnose's hypothesise phase, design-twice loops). The quick-ref in `~/.claude/CLAUDE.md` covers casual use; this file covers the full discipline plus principles, relationships, and rejected framings.

---

## Module

Anything with an interface and an implementation. Deliberately scale-agnostic — applies equally to a function, a class, a package, or a tier-spanning slice. A pure helper is a module; the entire Assistant subsystem is also a module. Resist substituting "unit," "component," or "service"; those words have prior commitments to test scope, framework conventions, and microservice deployment respectively.

A module has **exactly one interface** — the surface it presents to callers and tests. Behind that interface, it may contain other modules with their own internal interfaces (an internal seam, see below). Those internal modules are still modules; their interfaces just aren't part of the parent's interface.

Example: `app/Modules/Assistant/Services/AssistantService.php` in an assistant app is one module. Its `respond($input)` entry point is the interface; the routing-to-pattern-matcher / Ollama / cloud-API logic lives behind it. The pattern matcher inside is itself a module, with its own (internal) interface used only by the parent.

---

## Interface

Everything a caller must know to use the module correctly. Includes the type signature (parameter list, return type), but also: invariants, ordering constraints, error modes, required configuration, performance characteristics, and side effects. "The function returns a `User` or throws `UserNotFound`; you must call `connect()` first; expect ~50ms p99" — all of that is the interface.

Reject "API" and "signature" as substitutes. "API" drifts toward HTTP. "Signature" refers only to the type-level surface, which is the thinnest possible slice of an interface.

The interface is also the **test surface**: tests cross the same seam as callers. If a test reaches past the interface to exercise behaviour, the module is the wrong shape (either too shallow, or the seam is in the wrong place).

Example: `memory_propose` has a small type signature (`kind`, `headline`, `claim`, optional `audience`) but its full interface includes: the approval queue (a fact or decision writes a tile and persists only when the owner approves it; a defect saves at once unless it carries `closes` or lands near an existing record), `rejected` being required when the `kind` is a decision, `flags` and `neighbours` coming back as evidence the caller must read before deciding the proposal stands, and the headline cap of 100 characters. A caller who knows only the signature cannot use it correctly.

Related: **seam** (where the interface lives), **depth** (how much leverage the interface yields).

---

## Depth

Leverage at the interface — the amount of behaviour a caller (or test) can exercise per unit of interface they have to learn. A module is **deep** when a large amount of behaviour sits behind a small interface. A module is **shallow** when the interface is nearly as complex as the implementation (a pass-through, a thin wrapper, a façade that re-exports half its internals).

**Depth is a property of the interface, not the implementation.** A deep module can be internally composed of many small, mockable, swappable parts — they just aren't part of the interface. Conversely, a 1000-line implementation behind a 17-method public surface is shallow despite its bulk: the caller has to learn 17 things.

We reject Ousterhout's "depth = ratio of implementation-lines to interface-lines" framing because it rewards padding the implementation. Depth-as-leverage is the operative definition.

Example: Laravel's `Eloquent\Model` is deep — `User::find(1)->orders()->where('paid', true)->get()` exercises connection management, query building, hydration, relationship loading, and identity map, behind a tiny interface. Compare to a hand-rolled `UserRepository` that exposes `findById`, `findByEmail`, `findActive`, `findActiveByRole`, `findActiveByRoleAndTenant`… — same logic, much wider interface, shallower module.

---

## Seam *(from Michael Feathers)*

A place where you can alter behaviour without editing in that place. The **location** at which a module's interface lives. Choosing where to put the seam is its own design decision, distinct from what goes behind it.

Reject "boundary" as a substitute — it's overloaded with DDD's bounded-context meaning. Say **seam** when you mean the swap-point, **interface** when you mean the contract there, **module** when you mean the thing.

A module has an **external seam** (where callers and tests meet its interface) and may have **internal seams** (private to its implementation, used by its own tests). Don't expose internal seams through the external interface just because tests use them.

**Seam discipline:** *one adapter means a hypothetical seam; two adapters means a real one.* Don't introduce a seam unless something actually varies across it — typically production-adapter plus test-adapter, or two production adapters. A single-adapter seam is just indirection.

Example: an assistant app's AI router has a real seam at the provider boundary — `OllamaProvider` and `AnthropicProvider` and `OpenAIProvider` all satisfy the same interface (`generate($prompt): Response`), and tests use an in-memory `FakeProvider`. Three adapters, two-of-which-are-production. A real seam, earning its keep.

Counter-example: a `UserRepository` interface with one implementation (`EloquentUserRepository`) and no test fake — that's a hypothetical seam, indirection without payoff. Either add the test fake (making it real) or inline the repo (removing the seam).

Related: **adapter** (what sits at the seam), **interface** (what the seam exposes).

---

## Adapter

A concrete thing that satisfies an interface at a seam. Describes **role** — what slot it fills — not substance, not what's inside. The same code can be a small adapter wrapping a large implementation (a Postgres-backed repository: tiny adapter surface, deep implementation) or a large adapter wrapping a small implementation (an in-memory fake: more adapter glue, trivial body). Reach for "adapter" when the seam is the topic; reach for "implementation" when the body is the topic.

Adapters categorise the **dependency** the deepened module sits across:

- **In-process** — pure compute, no adapter needed, deepen directly.
- **Local-substitutable** — local stand-in exists (PGLite for Postgres, in-memory filesystem). Adapter is internal; tests use the stand-in. No port at the module's external interface.
- **Remote but owned** — your own services across a network (microservices, internal APIs). Define a **port** at the seam; implement an HTTP/gRPC/queue **adapter** for production, an in-memory adapter for tests.
- **True external** — third-party services you don't control (Stripe, Twilio). Inject a port; tests provide a mock adapter; production has a real-API adapter.

Example: a web app's API client layer (`src/api/*.ts`) is an **adapter** sitting between the Vue views and the backend's HTTP API. The seam is the function signatures the views call; the adapter translates view calls into `fetch` calls. Tests stub the adapter at the seam, not at `fetch`, so the views can be exercised without a network.

Related: **seam** (where adapters live), **port** (the interface a remote-but-owned adapter satisfies — same thing as interface, named to signal the dependency category).

---

## Leverage

What **callers** get from depth. More capability per unit of interface they have to learn. One implementation pays back across N call sites and M tests — write the hard logic once, exercise it everywhere with thin invocations.

Leverage is the user-facing payoff of depth. When you propose deepening a module, "leverage" is the word for the value delivered to the people writing call sites. The matching word for the maintainer's payoff is **locality** (below).

Example: a Laravel app's `BroadcastsTo` Reverb wiring — one declaration on a model wires up channel name, authorization, and payload shape. N controllers and M frontend listeners all get correct broadcasts from one line of caller code. High leverage: small interface (the trait), large behaviour (the whole broadcast pipeline).

---

## Locality

What **maintainers** get from depth. Change, bugs, knowledge, and verification concentrate at one place rather than spreading across callers. Fix once, fixed everywhere. Read once, understood everywhere.

Locality is the maintainer-facing payoff of depth. When you propose deepening, "locality" is the word for the reduction in coordinated edits a future change will require. The matching word for the caller's payoff is **leverage** (above).

The **deletion test** probes for locality: imagine deleting the module. If complexity vanishes, the module wasn't earning locality (it was a pass-through that just moved code around). If complexity reappears across N callers, the module was concentrating complexity that would otherwise spread — high locality, earning its keep.

Example: a shop backend's order-state machine module concentrates all valid-transition logic in one place. A new shipping carrier adds states by editing one file; without that locality, every controller, every job, every Blade view that touched order status would need a coordinated edit. Locality is what makes "add a state" a one-PR change instead of a multi-day audit.

---

## Principles

- **Depth is a property of the interface, not the implementation.** A deep module can be internally composed of small mockable parts — they just aren't part of the interface. A module can have **internal seams** (private to its implementation, used by its own tests) as well as the **external seam** at its interface.
- **The deletion test.** Imagine deleting the module. If complexity vanishes, the module wasn't hiding anything (it was a pass-through). If complexity reappears across N callers, the module was earning its keep.
- **The interface is the test surface.** Callers and tests cross the same seam. If you want to test *past* the interface, the module is probably the wrong shape.
- **One adapter means a hypothetical seam. Two adapters means a real one.** Don't introduce a seam unless something actually varies across it.
- **Replace, don't layer (testing).** Once tests exist at the deepened module's interface, old unit tests on the absorbed shallow modules become waste — delete them.
- **Tests assert on observable outcomes through the interface, not internal state.** Tests should survive internal refactors. If a test must change when the implementation changes, it's testing past the interface.

## Relationships

- A **Module** has exactly one **Interface** (the surface it presents to callers and tests).
- **Depth** is a property of a **Module**, measured against its **Interface**.
- A **Seam** is where a **Module**'s **Interface** lives.
- An **Adapter** sits at a **Seam** and satisfies the **Interface**.
- **Depth** produces **Leverage** for callers and **Locality** for maintainers.
- A **Port** is an **Interface** named to signal a remote-but-owned dependency category.

## Rejected framings

- **Depth as ratio of implementation-lines to interface-lines** (Ousterhout): rewards padding the implementation. We use depth-as-leverage instead.
- **"Interface" as the TypeScript `interface` keyword or a class's public methods**: too narrow — interface here includes every fact a caller must know.
- **"Boundary"**: overloaded with DDD's bounded context. Say **seam** or **interface**.
- **"Component" / "Service" / "Unit"** as substitutes for **Module**: each carries framework-specific or test-scope baggage. Say **module**.

## Design-it-twice (interface design)

When exploring alternative interfaces for a chosen deepening candidate, spawn 3+ sub-agents in parallel. Each must produce a **radically different** interface for the deepened module. Each agent gets a different design constraint:

- Agent 1: minimise the interface — 1–3 entry points, maximise leverage per entry point.
- Agent 2: maximise flexibility — support many use cases and extension.
- Agent 3: optimise for the most common caller — make the default case trivial.
- Agent 4 (if relevant): design around ports & adapters for cross-seam dependencies.

Each sub-agent outputs: (1) interface (types, methods, invariants, ordering, error modes); (2) usage example; (3) what the implementation hides behind the seam; (4) dependency strategy and adapters; (5) trade-offs — where leverage is high, where it's thin.

Present sequentially, then compare in prose. Contrast by **depth** (leverage at the interface), **locality** (where change concentrates), and **seam placement**. Give an opinionated recommendation; propose hybrids where elements combine well.
