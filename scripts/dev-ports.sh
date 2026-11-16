#!/usr/bin/env bash
SKILLBOOK="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd -P)"
source "$SKILLBOOK/hooks/scope-map.sh" 2>/dev/null

declare -A docker_names=()
WANTED=("$@")

load_docker_ports() {
  local name ports port
  command -v docker >/dev/null 2>&1 || return 0

  while IFS=$'\t' read -r name ports; do
    while read -r port; do
      [ -n "$port" ] && docker_names[$port]="$name"
    done < <(grep -oE '(0\.0\.0\.0|\[::\]|127\.0\.0\.1):[0-9]+->' <<<"$ports" | sed -E 's/.*:([0-9]+)->/\1/')
  done < <(timeout 5 docker ps --format '{{.Names}}	{{.Ports}}' 2>/dev/null)
}

repo_of_pid() {
  local cwd
  cwd=$(readlink "/proc/$1/cwd" 2>/dev/null) || return 1
  [ -d "$cwd" ] || return 1

  if declare -F main_checkout >/dev/null; then
    basename "$(main_checkout "$cwd" 2>/dev/null || echo "$cwd")"
  else
    basename "$cwd"
  fi
}

wanted() {
  local port
  [ "${#WANTED[@]}" -gt 0 ] || return 0

  for port in "${WANTED[@]}"; do
    [ "$port" = "$1" ] && return 0
  done
  return 1
}

owner_of() {
  local port="$1" users="$2" pid cmd repo

  pid=$(grep -oE 'pid=[0-9]+' <<<"$users" | head -1 | cut -d= -f2)
  if [ -n "$pid" ]; then
    cmd=$(ps -o comm= -p "$pid" 2>/dev/null)
    repo=$(repo_of_pid "$pid" || echo "?")
    echo "pid=$pid cmd=${cmd:-?} repo=$repo"
  elif [ -n "${docker_names[$port]:-}" ]; then
    echo "docker container=${docker_names[$port]}"
  else
    echo "unknown"
  fi
}

main() {
  local users port seen="" line scan err errfile
  load_docker_ports

  errfile=$(mktemp)
  scan=$(ss -H -ltnp 2>"$errfile")
  err=$(cat "$errfile")
  rm -f "$errfile"

  if [ -n "$err" ] || ! command -v ss >/dev/null 2>&1; then
    echo "scan-unavailable: ss could not list listeners, so no port can be called free"
    return 0
  fi

  while read -r port users; do
    [[ "$port" =~ ^[0-9]+$ ]] || continue
    wanted "$port" || continue

    line=$(printf '%-6s %s' "$port" "$(owner_of "$port" "$users")")
    [[ "$seen" == *"|$line|"* ]] && continue

    seen="$seen|$line|"
    echo "$line"
  done < <(awk '{u=""; for(i=5;i<=NF;i++) if($i ~ /^users:/) u=$i; n=split($4,a,":"); print a[n], u}' <<<"$scan" | sort -n -k1,1)
}

main "$@"
exit 0
