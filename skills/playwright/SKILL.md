---
name: playwright
description: >
  Browser verification through the Playwright MCP: page loads, console and
  network errors, screenshots, and multi-step flows. Triggers: playwright,
  browser test, frontend test, UI test, visual check, smoke test, e2e, verify
  page, screenshot, browser verification.
allowed-tools: Bash(*/skill-project.sh *)
---

# Playwright

## Port check

Before any browser pass or dev-server start, run `$HOME/.claude/skills/../scripts/dev-ports.sh` (add the expected port to filter). Project additions give the target repo's expected port, app marker, and whether the backend pins origins.

- Expected port owned by the target repo: use it.
- `scan-unavailable` is not "free": the listener scan failed, so check the port another way before starting.
- Free: start the server there and confirm the bound port from the server's log, because Nuxt falls back to another port without saying so.
- Held by another repo or process: pick a free port only when Project additions say the backend does not pin origins; otherwise stop and report who holds it.
- Before trusting a page, check the app marker (title or another stable element). A taken port can serve a different app that looks plausible.

## Driving the browser

Use the Playwright MCP tools (`browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`, `browser_evaluate`, and the rest of `browser_*`). Each snapshot returns the full accessibility tree (~5-10k tokens), so prefer targeted checks over repeated snapshots.

Page-load, smoke, and visual checks: `browser_navigate` to each route, then `browser_console_messages({ level: "error" })` and `browser_network_requests` for 4xx/5xx, then `browser_take_screenshot` and `Read` the PNG.

### Pre-flight (run before any flow)

1. **FE gate** — `curl -s -o /dev/null -w "%{http_code}" <fe_url>`. If not 200, start the dev server and poll until ready.
2. **Auth** — read the repo's `.claude/PW_CREDS.md` first; recall project memory for the auth/impersonation recipe only when it is missing. Do this once per session before navigating.
3. **Data** — if test data is needed, use factories via tinker (not hand-built inserts). Check `Schema::getColumnListing` first if no factory exists.
4. **Routes** — grep the FE route definitions, don't guess paths; Project additions name where they live.
5. **Console gate** — after each navigation, run `browser_console_messages({ level: "error" })`. Flag 4xx/5xx fetches or JS exceptions before proceeding.

- **Clipped elements pass snapshots.** `browser_snapshot` lists CSS-clipped or zero-area elements as visible nodes and `browser_click` clicks them. For a dropdown, overlay or menu visibility claim, take a `browser_take_screenshot` and look, or compare `getBoundingClientRect` with the clipping ancestor.
- **`browser_route` patterns** need a trailing wildcard for endpoints called with a query string: `**/api/path*`. `**/api/path` does not match `**/api/path?x=1`, and the request silently reaches the real backend.
- **Cleanup.** When the pass ends, `browser_close` and stop the dev servers and containers you started.

## Local URLs

Project additions give each repo's local URLs.

Self-signed certs accepted. Port 81 explicitly allowed. Authenticated pages use cookie/token injection; the recipe is in Pre-flight step 2.

## Project additions

!`$HOME/.claude/skills/../scripts/skill-project.sh playwright`

If the line above shows a raw command instead of content, run it.
