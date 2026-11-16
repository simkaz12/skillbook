# Laravel build and review standard

Apply this when the repository uses Laravel, except CRM (`crm-api`, `crm-web`, Tabularium scope `crm`). CRM follows its own repository architecture, conventions, and agreed brief; do not apply this standard or raise review findings against it there.

For other Laravel repositories, read the repo's own conventions and the brief first. An explicit user instruction, a repo convention, or a concrete framework requirement may justify a different shape; name that reason and its effect in the verdict. A passing test suite does not waive these rules.

- Validate and authorize incoming requests in Form Requests at the entry point. Validate commands, jobs, and other non-request inputs before they reach domain methods. Keep business decisions out of validation classes.
- Pass structured domain data through native typed signatures and readonly DTOs, including nested values. Use backed enums for closed value sets. Do not substitute `mixed`, loose associative arrays, or PHPDoc alone for structured domain values. Use documented typed collections where PHP has no native generic type. Keep arrays at wire and persistence edges.
- Use Eloquent models, relationships, and scopes for ordinary model access. Avoid raw table queries and generic model dispatch when Eloquent expresses the operation clearly. A concrete query or performance need can justify an exception.
- Keep access control in middleware, input mapping at entry, domain operations in domain modules, and output shaping in Resources or explicit response DTOs. Resolve owner and request context once at entry and pass it explicitly.
- Prefer guards and sequential steps over nested callbacks. Use `match` or `switch` for exclusive alternatives. Use collection or set operations for simple transforms and membership checks; retain loops when order, side effects, or indexed errors matter.
- Extract methods that name a real operation. Avoid tiny pass-through wrappers, boolean switches that hide separate operations, and speculative generic frameworks.
- Preserve stored instants, date-only values, missing values, and explicit `null` distinctly. Convert to the project's configured display timezone only where the interface calls for it; never relabel a UTC instant as local time or hardcode a project-specific timezone here.
- Implement only the agreed product scope. Do not invent observations, quantities, defaults, or user decisions. Review readability and data meaning separately from whether tests pass.
