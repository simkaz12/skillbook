### t3code

| Build branch | Merge | Rebuild |
|---|---|---|
| `dev` | merge commit | desktop tar.gz, staged for the owner to swap |

The fork has no Blacksmith runners, so every workflow that runs on them (CI, release, mobile, preview, Windows tests) is disabled in the repo's Actions settings (2026-11-01). Only the GitHub-hosted label and budget checks report on a PR; merge once they pass. If an upstream merge adds a new Blacksmith workflow, disable it with `gh workflow disable <file> --repo <owner>/t3code`. The commit body ends with the model and harness line too, for example `Opus 5.5 via Claude Code`, as land's PR body does.

**Rebuild.**

1. In the background (it takes about ten minutes): `cp -n .env.example .env; PATH="$PWD/node_modules/.bin:$PATH" NODE_OPTIONS=--max-old-space-size=4096 node scripts/build-desktop-artifact.ts --platform linux --target tar.gz --arch x64 > /tmp/t3-zero-build.log 2>&1`. On failure, print the log tail and stop.
2. Take the newest artifact, `ls -t release/T3-Code-*-x64.tar.gz | head -1`, and check that its mtime falls inside this run. `release/` still holds older tarballs.
3. Stage it: `rm -rf ~/.local/opt/t3code-fork.new && mkdir -p ~/.local/opt/t3code-fork.new && tar -xzf <artifact> -C ~/.local/opt/t3code-fork.new --strip-components=1`.
4. Never swap it yourself. This session usually runs inside the installed app. Hand the owner this line, to run after quitting T3 Code:

```
rm -rf ~/.local/opt/t3code-fork.prev && mv ~/.local/opt/t3code-fork ~/.local/opt/t3code-fork.prev && mv ~/.local/opt/t3code-fork.new ~/.local/opt/t3code-fork
```

The `rm` matters. With an old `.prev` still in place, `mv` nests the current install inside it instead of replacing it.
