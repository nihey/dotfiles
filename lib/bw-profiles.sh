#!/usr/bin/env bash
# Machine-local Bitwarden CLI profile setup. Sourced by install.sh.
# Server URLs are prompted (or passed as $2 in tests) and never stored in git.

bw_config_home() {
  printf '%s' "${XDG_CONFIG_HOME:-$HOME/.config}"
}

bw_profile_configure() {
  local profile="${1:-}"
  local url="${2:-}"
  local home server_file

  case "$profile" in
    quickfiller | kassellabs | nihey) ;;
    *)
      echo "bw_profile_configure: unknown profile: $profile" >&2
      return 2
      ;;
  esac

  home="$(bw_config_home)"
  mkdir -p "$home/bw-$profile"
  chmod 700 "$home/bw-$profile"
  server_file="$home/bw-$profile/server"

  if [[ -s "$server_file" ]]; then
    echo "bw-$profile: already configured"
    return 0
  fi

  if [[ -z "$url" ]]; then
    if [[ -t 0 ]]; then
      read -r -p "Server URL for bw-$profile: " url
    else
      read -r url || true
    fi
  fi

  if [[ -z "$url" ]]; then
    echo "bw-$profile: skipped (no server URL)" >&2
    return 0
  fi

  if [[ ! "$url" =~ ^https://[^[:space:]]+$ ]]; then
    echo "bw-$profile: URL must be https and contain no spaces" >&2
    return 1
  fi

  printf '%s\n' "$url" >"$server_file"
  chmod 600 "$server_file"

  if ! command -v bw >/dev/null 2>&1; then
    echo "bw-$profile: saved URL; install the Bitwarden CLI (bw) to use it"
    return 0
  fi

  local bw_out=""
  local bw_status=0
  if [[ "$profile" == "nihey" ]]; then
    bw_out="$(env -u BITWARDENCLI_APPDATA_DIR bw config server "$url" 2>&1)" || bw_status=$?
  else
    bw_out="$(BITWARDENCLI_APPDATA_DIR="$home/bw-$profile" bw config server "$url" 2>&1)" || bw_status=$?
  fi
  if [[ "$bw_status" -ne 0 ]]; then
    if [[ "$bw_out" == *"Logout required"* ]]; then
      echo "bw-$profile: URL saved (existing bw session already has a server)"
      return 0
    fi
    printf '%s\n' "$bw_out" >&2
    return "$bw_status"
  fi
  echo "bw-$profile: configured"
}
