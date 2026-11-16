### skillbook

| Build branch | Merge | Rebuild |
|---|---|---|
| `master` | merge commit | none, live once `master` is pulled |

Land's worktree rule applies here. The live checkout never leaves `master`, because `~/.claude/skills` points into it. Remove the worktree before deleting the branch; the pull after the merge makes the change live.
