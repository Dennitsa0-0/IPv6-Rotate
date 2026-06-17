#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: run as root"
  exit 1
fi

systemctl disable --now ipv6-rotate.timer 2>/dev/null || true
rm -f /etc/systemd/system/ipv6-rotate.timer
rm -f /etc/systemd/system/ipv6-rotate.service
systemctl daemon-reload 2>/dev/null || true
rm -f /usr/local/bin/ipv6-rotate
rm -f /usr/local/bin/ipv6-rotate.sh
rm -f /usr/local/bin/ipv6-rotate-cli.py

if [[ "${1:-}" == "--purge" ]]; then
  rm -f /etc/default/ipv6-rotate
  rm -rf /var/lib/ipv6-rotate
  rm -f /var/log/ipv6-rotate.log
  echo "Purged config/state/logs."
fi

echo "Uninstalled ipv6-rotate."
if [[ "${1:-}" != "--purge" ]]; then
  echo "Kept config/state/logs:"
  echo "  /etc/default/ipv6-rotate"
  echo "  /var/lib/ipv6-rotate/state.json"
  echo "  /var/log/ipv6-rotate.log"
fi
