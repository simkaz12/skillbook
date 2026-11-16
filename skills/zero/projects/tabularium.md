### tabularium

| Build branch | Merge | Rebuild |
|---|---|---|
| `main` | merge commit | `./deploy.sh` |

**Rebuild.** Run `./deploy.sh` from the repo root in the background. It pulls `main` on the host, runs `uv sync`, waits for cleaner judge processes to drain (up to 30 minutes) and restarts `tabularium-mcp.service`. A drain timeout means it did not restart. Report that and never force the restart. Memory tools drop out for a moment while the service restarts.
