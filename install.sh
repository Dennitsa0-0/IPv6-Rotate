#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="/etc/default/ipv6-rotate"
ASSUME_YES=0
DRY_RUN=0
ENABLE_TIMER=1

for arg in "$@"; do
  case "$arg" in
    --yes|-y) ASSUME_YES=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --no-enable-timer) ENABLE_TIMER=0 ;;
    --help|-h)
      cat <<EOF
Usage: bash install.sh [--dry-run] [--yes] [--no-enable-timer]

  --dry-run          show detected values and planned actions without installing
  --yes, -y          do not ask for confirmation
  --no-enable-timer  install files but do not enable/start ipv6-rotate.timer
EOF
      exit 0
      ;;
    *) echo "ERROR: unknown option: $arg"; exit 2 ;;
  esac
done

if [[ -f "${ROOT_DIR}/.env" ]]; then
  # shellcheck disable=SC1091
  . "${ROOT_DIR}/.env"
fi

PREFIX="${PREFIX:-}"
IFACE="${IFACE:-}"
GATEWAY="${GATEWAY:-}"
KEEP_ADDRS="${KEEP_ADDRS:-}"
LANGUAGE="${LANGUAGE:-auto}"
INTERVAL="${INTERVAL:-10min}"
GRACE_SECONDS="${GRACE_SECONDS:-1800}"
MAX_OLD_ADDRS="${MAX_OLD_ADDRS:-10}"
HEALTHCHECK_PING6="${HEALTHCHECK_PING6:-2606:4700:4700::1111 2001:4860:4860::8888}"
HEALTHCHECK_URLS="${HEALTHCHECK_URLS:-https://ifconfig.me https://api64.ipify.org}"
HEALTHCHECK_MODE="${HEALTHCHECK_MODE:-strict}"
WEBHOOK_URL="${WEBHOOK_URL:-}"
LOG_FILE="${LOG_FILE:-/var/log/ipv6-rotate.log}"

detect_defaults() {
  local route first_addr detected_prefix
  route="$(ip -6 route show default 2>/dev/null | head -n1 || true)"

  [[ -n "$IFACE" ]] || IFACE="$(awk '{for (i=1; i<=NF; i++) if ($i=="dev") {print $(i+1); exit}}' <<< "$route")"
  [[ -n "$GATEWAY" ]] || GATEWAY="$(awk '{for (i=1; i<=NF; i++) if ($i=="via") {print $(i+1); exit}}' <<< "$route")"

  if [[ -z "$PREFIX" && -n "$IFACE" ]]; then
    first_addr="$(ip -o -6 addr show dev "$IFACE" scope global | awk '{print $4; exit}')"
    if [[ -n "$first_addr" ]]; then
      detected_prefix="$(python3 - "$first_addr" <<'PY'
import ipaddress
import sys
iface = ipaddress.ip_interface(sys.argv[1])
print(":".join(part.lstrip("0") or "0" for part in iface.ip.exploded.split(":")[:4]))
PY
)"
      PREFIX="$detected_prefix"
    fi
  fi
}

confirm_detected() {
  if [[ "${ASSUME_YES:-0}" == "1" ]]; then
    return 0
  fi

  cat <<EOF
Detected/configured:
IFACE=${IFACE}
GATEWAY=${GATEWAY}
PREFIX=${PREFIX}
KEEP_ADDRS=${KEEP_ADDRS}
LANGUAGE=${LANGUAGE}
INTERVAL=${INTERVAL}
GRACE_SECONDS=${GRACE_SECONDS}
MAX_OLD_ADDRS=${MAX_OLD_ADDRS}
HEALTHCHECK_MODE=${HEALTHCHECK_MODE}

Run installer with these values? [y/N]
EOF
  read -r answer
  [[ "$answer" == "y" || "$answer" == "Y" || "$answer" == "yes" || "$answer" == "YES" ]]
}

backup_if_exists() {
  local file="$1"
  local ts
  ts="$(date +%F-%H%M%S)"
  if [[ -e "$file" || -L "$file" ]]; then
    cp -a "$file" "${file}.bak.${ts}"
    echo "Backup: ${file}.bak.${ts}"
  fi
}

warn_timer_override() {
  if [[ -f /etc/systemd/system/ipv6-rotate.timer.d/override.conf ]]; then
    echo "Notice: existing timer override found:"
    echo "  /etc/systemd/system/ipv6-rotate.timer.d/override.conf"
    echo "Runtime interval may be controlled by this override."
  fi
}

detect_defaults

CONFIG_COMPLETE=1
[[ -n "$PREFIX" ]] || CONFIG_COMPLETE=0
[[ -n "$IFACE" ]] || CONFIG_COMPLETE=0
[[ -n "$GATEWAY" ]] || CONFIG_COMPLETE=0
[[ -n "$KEEP_ADDRS" ]] || CONFIG_COMPLETE=0

if [[ "$DRY_RUN" == "1" ]]; then
  cat <<EOF
Dry run only. Would install:
  /usr/local/bin/ipv6-rotate
  /usr/local/bin/ipv6-rotate-cli.py
  ${CONFIG_FILE}
  /etc/systemd/system/ipv6-rotate.service
  /etc/systemd/system/ipv6-rotate.timer

Detected/configured:
  IFACE=${IFACE}
  GATEWAY=${GATEWAY}
  PREFIX=${PREFIX}
  KEEP_ADDRS=${KEEP_ADDRS}
  LANGUAGE=${LANGUAGE}
  GRACE_SECONDS=${GRACE_SECONDS}
  MAX_OLD_ADDRS=${MAX_OLD_ADDRS}
  HEALTHCHECK_MODE=${HEALTHCHECK_MODE}
Timer interval: ${INTERVAL}
Timer enable: $([[ "$ENABLE_TIMER" == "1" ]] && echo yes || echo no)
EOF
  warn_timer_override
  exit 0
fi

confirm_detected || {
  echo "Cancelled."
  exit 1
}

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: run as root"
  exit 1
fi

backup_if_exists /usr/local/bin/ipv6-rotate
backup_if_exists /usr/local/bin/ipv6-rotate.sh
backup_if_exists /usr/local/bin/ipv6-rotate-cli.py
backup_if_exists "$CONFIG_FILE"
backup_if_exists /etc/systemd/system/ipv6-rotate.service
backup_if_exists /etc/systemd/system/ipv6-rotate.timer

install -m 0755 "${ROOT_DIR}/ipv6-rotate" /usr/local/bin/ipv6-rotate
install -m 0644 "${ROOT_DIR}/cli.py" /usr/local/bin/ipv6-rotate-cli.py
ln -sf /usr/local/bin/ipv6-rotate /usr/local/bin/ipv6-rotate.sh

cat > "$CONFIG_FILE" <<EOF
IFACE="${IFACE}"
PREFIX="${PREFIX}"
GATEWAY="${GATEWAY}"
KEEP_ADDRS="${KEEP_ADDRS}"
LANGUAGE="${LANGUAGE}"
GRACE_SECONDS="${GRACE_SECONDS}"
MAX_OLD_ADDRS="${MAX_OLD_ADDRS}"
HEALTHCHECK_PING6="${HEALTHCHECK_PING6}"
HEALTHCHECK_URLS="${HEALTHCHECK_URLS}"
HEALTHCHECK_MODE="${HEALTHCHECK_MODE}"
WEBHOOK_URL="${WEBHOOK_URL}"
LOG_FILE="${LOG_FILE}"
EOF

install -m 0644 "${ROOT_DIR}/ipv6-rotate.service" /etc/systemd/system/ipv6-rotate.service
sed "s|\${INTERVAL}|${INTERVAL}|g" "${ROOT_DIR}/ipv6-rotate.timer" > /etc/systemd/system/ipv6-rotate.timer

systemctl daemon-reload
warn_timer_override

echo
if [[ "$CONFIG_COMPLETE" == "1" ]]; then
  if /usr/local/bin/ipv6-rotate validate; then
    if [[ "$ENABLE_TIMER" == "1" ]]; then
      systemctl enable --now ipv6-rotate.timer
    else
      echo "Timer was not enabled (--no-enable-timer)."
    fi
    echo "Installed."
  else
    echo "Installed, but validation failed."
    echo "The timer was not enabled."
    echo
    echo "Run:"
    echo "  sudo ipv6-rotate setup"
    echo "  sudo ipv6-rotate validate"
    echo "  sudo systemctl enable --now ipv6-rotate.timer"
  fi
else
  echo "Installed, but configuration is incomplete."
  echo "The timer was not enabled."
  echo
  echo "Run:"
  echo "  sudo ipv6-rotate setup"
  echo "  sudo ipv6-rotate validate"
  echo "  sudo systemctl enable --now ipv6-rotate.timer"
fi
echo "Config: ${CONFIG_FILE}"
echo "Command: /usr/local/bin/ipv6-rotate"
echo
echo "Try:"
echo "  ipv6-rotate status"
echo "  ipv6-rotate dry-run"
echo "  ipv6-rotate rotate"
echo "  ipv6-rotate doctor"
echo "  ipv6-rotate menu"
