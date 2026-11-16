#!/usr/bin/env bash
SKILLBOOK="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd -P)"
skill="${1:-}"

source "$SKILLBOOK/hooks/scope-map.sh" 2>/dev/null || { echo none; exit 0; }

if [ -n "$skill" ]; then
  print_additions "$SKILLBOOK/skills/$skill/projects" .md . 2>/dev/null || echo none
else
  echo none
fi
exit 0
