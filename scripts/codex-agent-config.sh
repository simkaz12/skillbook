codex_model_supported() {
  case "$1" in
    sol | luna | gpt-6-astra | gpt-6.1-sol | gpt-6-sol | gpt-6-luna | gpt-5.6-sol | gpt-5.6-terra | gpt-5.6-luna | gpt-5.5) return 0 ;;
    *) return 1 ;;
  esac
}

codex_effort_supported() {
  case "$1" in
    low | medium | high | xhigh | max | ultra) return 0 ;;
    *) return 1 ;;
  esac
}

codex_model_for_claude_model() {
  case "$1" in
    haiku) echo luna ;;
    sonnet) echo sol ;;
    *) return 1 ;;
  esac
}

codex_resolve_model() {
  local family="$1"
  case "$family" in
    sol | luna) ;;
    *) printf '%s\n' "$family"; return ;;
  esac

  local catalog="${CODEX_HOME:-$HOME/.codex}/models_cache.json" model
  if ! model=$(jq -er --arg family "$family" '
    .models
    | map(
        select(.visibility == "list")
        | .slug
        | select(type == "string")
        | select(test("^gpt-[0-9]+(\\.[0-9]+)*-" + $family + "$"))
      )
    | max_by(ltrimstr("gpt-") | rtrimstr("-" + $family) | split(".") | map(tonumber))
    // empty
  ' "$catalog"); then
    echo "Cannot resolve latest $family model from $catalog; refresh the Codex model catalog and retry." >&2
    return 1
  fi

  printf '%s\n' "$model"
}
