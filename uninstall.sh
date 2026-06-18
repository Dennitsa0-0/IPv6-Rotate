#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="${CONFIG_FILE:-/etc/default/ipv6-rotate}"

if [[ -f "${CONFIG_FILE}" ]]; then
  # shellcheck disable=SC1090
  . "${CONFIG_FILE}"
fi

lang() {
  case "${LANGUAGE:-auto}" in
    ru) echo "ru" ;;
    en) echo "en" ;;
    auto)
      case "${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}" in
        ru*|RU*|*.ru*|*.RU*) echo "ru" ;;
        *) echo "en" ;;
      esac
      ;;
    *) echo "en" ;;
  esac
}

msg() {
  local key="$1"
  case "$(lang):${key}" in
    ru:usage) echo "Использование: bash uninstall.sh [--purge]" ;;
    ru:help_purge) echo "  --purge  удалить конфиг, state и логи" ;;
    ru:run_as_root) echo "ОШИБКА: запустите от root" ;;
    ru:uninstalled) echo "Удалено: ipv6-rotate" ;;
    ru:kept) echo "Конфиг/state/logs сохранены:" ;;
    ru:purged) echo "Конфиг/state/logs удалены." ;;
    ru:unknown_option) echo "ОШИБКА: неизвестная опция: $2" ;;
    en:usage|*:usage) echo "Usage: bash uninstall.sh [--purge]" ;;
    en:help_purge|*:help_purge) echo "  --purge  delete config, state, and logs" ;;
    en:run_as_root|*:run_as_root) echo "ERROR: run as root" ;;
    en:uninstalled|*:uninstalled) echo "Uninstalled ipv6-rotate." ;;
    en:kept|*:kept) echo "Kept config/state/logs:" ;;
    en:purged|*:purged) echo "Purged config/state/logs." ;;
    en:unknown_option|*:unknown_option) echo "ERROR: unknown option: $2" ;;
    *) echo "$key" ;;
  esac
}

PURGE=0
for arg in "$@"; do
  case "$arg" in
    --purge) PURGE=1 ;;
    --help|-h)
      echo "$(msg usage)"
      echo
      echo "$(msg help_purge)"
      exit 0
      ;;
    *) echo "$(msg unknown_option "$arg")"; exit 2 ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "$(msg run_as_root)"
  exit 1
fi

systemctl disable --now ipv6-rotate.timer 2>/dev/null || true
rm -f /etc/systemd/system/ipv6-rotate.timer
rm -f /etc/systemd/system/ipv6-rotate.service
rm -rf /etc/systemd/system/ipv6-rotate.timer.d
systemctl daemon-reload 2>/dev/null || true
rm -f /usr/local/bin/ipv6-rotate
rm -f /usr/local/bin/ipv6-rotate.sh
rm -f /usr/local/bin/ipv6-rotate-cli.py

if [[ "${PURGE}" == "1" ]]; then
  rm -f "${CONFIG_FILE}"
  rm -rf /var/lib/ipv6-rotate
  rm -f /var/log/ipv6-rotate.log
  echo "$(msg purged)"
fi

echo "$(msg uninstalled)"
if [[ "${PURGE}" != "1" ]]; then
  echo "$(msg kept)"
  echo "  ${CONFIG_FILE}"
  echo "  /var/lib/ipv6-rotate/state.json"
  echo "  /var/log/ipv6-rotate.log"
fi
