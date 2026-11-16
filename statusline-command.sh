#!/usr/bin/env bash
input=$(cat)

cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
model_id=$(echo "$input" | jq -r '.model.id // ""')
transcript=$(echo "$input" | jq -r '.transcript_path // ""')

ctx_window=200000
if [[ "$model_id" =~ ^claude-opus-4-([0-9]+) ]] && [ "${BASH_REMATCH[1]}" -ge 6 ]; then
  # Opus 4.6+ ships the 1M window (auto-enabled on Max/Team/Enterprise)
  ctx_window=1000000
elif echo "$model_id" | grep -q '\[1m\]'; then
  ctx_window=1000000
fi

input_tokens=0
if [ -n "$transcript" ] && [ -f "$transcript" ]; then
  input_tokens=$(tac "$transcript" 2>/dev/null \
    | jq -r 'select(.message.usage) | .message.usage | (.input_tokens // 0) + (.cache_read_input_tokens // 0) + (.cache_creation_input_tokens // 0)' 2>/dev/null \
    | head -n 1)
  input_tokens=${input_tokens:-0}
fi

if [ "$input_tokens" -ge 1000 ]; then
  token_k=$(( (input_tokens + 500) / 1000 ))
  token_display="${token_k}k"
else
  token_display="${input_tokens}"
fi

pct=$(awk -v t="$input_tokens" -v w="$ctx_window" 'BEGIN { printf "%.0f", (t / w) * 100 }')

project_name=$(basename "$cwd")
orange=$'\033[38;5;208m'

reset=$'\033[0m'
color=""
nudge=""
if [ "$pct" -ge 35 ]; then
  color=$'\033[1;91m'
  nudge="  → /clear when done"
elif [ "$pct" -ge 10 ]; then
  color=$'\033[1;93m'
fi

git_part=""
if [ -n "$cwd" ] && git -C "$cwd" rev-parse --git-dir > /dev/null 2>&1; then
  branch=$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null \
           || git -C "$cwd" rev-parse --short HEAD 2>/dev/null)
  git_part=" --- ${branch}"
fi

dim=$'\033[2m'

printf '%s───%s %s%s%s %s───%s\n' "$dim" "$reset" "$orange" "$project_name" "$reset" "$dim" "$reset"
printf '%s%s (%s%%)%s%s%s\n' "$color" "$token_display" "$pct" "$git_part" "$nudge" "$reset"
