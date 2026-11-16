scope_for_path() {
  local cwd="$1"
  local root="${PROJECTS_ROOT:-$HOME/Projects}"

  case "$cwd" in
    "$root"/crm-api*|"$root"/crm-web*)       echo crm ;;
    "$root"/Tabularium*|"$root"/tabularium*) echo tabularium ;;
    "$root"/arx*)                            echo arx ;;
    "$root"/skillbook*)                      echo skillbook ;;
    "$root"/t3code*)                         echo t3code ;;
    *) return 1 ;;
  esac
}

path_scope() {
  local cwd="$1" main

  scope_for_path "$cwd" && return 0

  main=$(main_checkout "$cwd") || return 1
  [ "$main" != "$cwd" ] || return 1

  scope_for_path "$main"
}

main_checkout() {
  local common
  common=$(git -C "${1:-.}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || return 1
  [ -n "$common" ] || return 1

  dirname "$common"
}

project_keys() {
  local main repo scope
  main=$(main_checkout "${1:-.}") || return 1
  repo=$(basename "$main")

  if scope=$(path_scope "$main") && [ "$scope" != "$repo" ]; then
    echo "$scope"
  fi
  echo "$repo"
}

print_additions() {
  local dir="$1" suffix="$2" cwd="${3:-.}"
  local key file out="" sep=""

  while IFS= read -r key; do
    file="$dir/${key}${suffix}"
    [ -f "$file" ] || continue

    out="${out}${sep}$(cat "$file" 2>/dev/null)"
    sep=$'\n\n'
  done < <(project_keys "$cwd")

  [ -n "$out" ] || return 1
  printf '%s\n' "$out"
}

base_branch() {
  local main repo
  main=$(main_checkout "${1:-.}") || return 1
  repo=$(basename "$main")

  if [ -n "${PULL_BASE_BRANCH:-}" ]; then
    echo "$PULL_BASE_BRANCH"
    return 0
  fi

  case "$repo" in
    crm-api|crm-web|t3code)     echo dev ;;
    skillbook)                  echo master ;;
    tabularium|Tabularium|arx)  echo main ;;
    *) return 1 ;;
  esac
}
