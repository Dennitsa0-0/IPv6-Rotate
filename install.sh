#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${CONFIG_FILE:-/etc/default/ipv6-rotate}"
TIMER_FILE="${TIMER_FILE:-/etc/systemd/system/ipv6-rotate.timer}"
TIMER_OVERRIDE_FILE="${TIMER_OVERRIDE_FILE:-/etc/systemd/system/ipv6-rotate.timer.d/override.conf}"
ASSUME_YES=0
DRY_RUN=0
ENABLE_TIMER=1
USE_ENV=0
ENV_LANGUAGE="${LANGUAGE:-}"

early_lang() {
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

early_msg() {
  local key="$1"
  case "$(early_lang):${key}" in
    ru:usage) echo "Использование: bash install.sh [--dry-run] [--yes] [--no-enable-timer] [--use-env]" ;;
    ru:help_dry_run) echo "  --dry-run          показать найденные значения и план без установки" ;;
    ru:help_yes) echo "  --yes, -y          не спрашивать подтверждение" ;;
    ru:help_no_enable) echo "  --no-enable-timer  установить файлы, но не включать ipv6-rotate.timer" ;;
    ru:help_use_env) echo "  --use-env          переустановить из .env, даже если установленный конфиг существует" ;;
    ru:use_env_missing) echo "ОШИБКА: передан --use-env, но ${ENV_FILE} не существует" ;;
    ru:unknown_option) echo "ОШИБКА: неизвестная опция: $2" ;;
    en:usage|*:usage) echo "Usage: bash install.sh [--dry-run] [--yes] [--no-enable-timer] [--use-env]" ;;
    en:help_dry_run|*:help_dry_run) echo "  --dry-run          show detected values and planned actions without installing" ;;
    en:help_yes|*:help_yes) echo "  --yes, -y          do not ask for confirmation" ;;
    en:help_no_enable|*:help_no_enable) echo "  --no-enable-timer  install files but do not enable/start ipv6-rotate.timer" ;;
    en:help_use_env|*:help_use_env) echo "  --use-env          reinstall from .env even when installed config exists" ;;
    en:use_env_missing|*:use_env_missing) echo "ERROR: --use-env was passed, but ${ENV_FILE} does not exist" ;;
    en:unknown_option|*:unknown_option) echo "ERROR: unknown option: $2" ;;
    *) echo "$key" ;;
  esac
}

print_help() {
  echo "$(early_msg usage)"
  echo
  echo "$(early_msg help_dry_run)"
  echo "$(early_msg help_yes)"
  echo "$(early_msg help_no_enable)"
  echo "$(early_msg help_use_env)"
}

for arg in "$@"; do
  case "$arg" in
    --yes|-y) ASSUME_YES=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --no-enable-timer) ENABLE_TIMER=0 ;;
    --use-env) USE_ENV=1 ;;
    --help|-h)
      print_help
      exit 0
      ;;
    *) echo "$(early_msg unknown_option "$arg")"; exit 2 ;;
  esac
done

CONFIG_SOURCE="auto-detect"
ENV_FILE="${ROOT_DIR}/.env"
ENV_OVERRIDES_CONFIG=0
ENV_IGNORED_FOR_SAFE_UPDATE=0

if [[ "${USE_ENV}" == "1" && ! -f "${ENV_FILE}" ]]; then
  echo "$(early_msg use_env_missing)"
  exit 2
elif [[ -f "${CONFIG_FILE}" && "${USE_ENV}" != "1" ]]; then
  # shellcheck disable=SC1090
  . "${CONFIG_FILE}"
  CONFIG_SOURCE="${CONFIG_FILE}"
  if [[ -f "${ENV_FILE}" ]]; then
    ENV_IGNORED_FOR_SAFE_UPDATE=1
  fi
elif [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1091
  . "${ENV_FILE}"
  CONFIG_SOURCE="${ENV_FILE}"
  if [[ -f "${CONFIG_FILE}" ]]; then
    ENV_OVERRIDES_CONFIG=1
  fi
fi

PREFIX="${PREFIX:-}"
IFACE="${IFACE:-}"
GATEWAY="${GATEWAY:-}"
KEEP_ADDRS="${KEEP_ADDRS:-}"
LANGUAGE="${LANGUAGE:-auto}"
OUTPUT_LANGUAGE="${ENV_LANGUAGE:-${LANGUAGE}}"
GRACE_SECONDS="${GRACE_SECONDS:-1800}"
MAX_OLD_ADDRS="${MAX_OLD_ADDRS:-10}"
HEALTHCHECK_PING6="${HEALTHCHECK_PING6:-2606:4700:4700::1111 2001:4860:4860::8888}"
HEALTHCHECK_URLS="${HEALTHCHECK_URLS:-https://ifconfig.me https://api64.ipify.org}"
HEALTHCHECK_MODE="${HEALTHCHECK_MODE:-strict}"
WEBHOOK_URL="${WEBHOOK_URL:-}"
LOG_FILE="${LOG_FILE:-/var/log/ipv6-rotate.log}"

lang() {
  case "${OUTPUT_LANGUAGE:-auto}" in
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
    ru:dry_run) echo "Пробный запуск. Будет установлено:" ;;
    ru:detected) echo "Найдено/настроено:" ;;
    ru:config_source) echo "Источник конфигурации" ;;
    ru:timer_interval) echo "Интервал таймера" ;;
    ru:timer_source) echo "Источник таймера" ;;
    ru:timer_override) echo "Override таймера" ;;
    ru:timer_enable) echo "Таймер будет включён" ;;
    ru:yes) echo "да" ;;
    ru:no) echo "нет" ;;
    ru:none) echo "нет" ;;
    ru:auto_detect) echo "автоопределение" ;;
    ru:run_installer) echo "Запустить installer с этими значениями? [y/N]" ;;
    ru:cancelled) echo "Отменено." ;;
    ru:run_as_root) echo "ОШИБКА: запустите от root" ;;
    ru:backup) echo "Бэкап" ;;
    ru:notice_both) echo "Обнаружены и .env, и ${CONFIG_FILE}." ;;
    ru:notice_env_source) echo "Используется .env как явный источник установки." ;;
    ru:notice_config_overwrite) echo "Существующая установленная конфигурация будет перезаписана после создания бэкапа." ;;
    ru:notice_env_ignored) echo ".env найден, но установленный конфиг тоже существует." ;;
    ru:notice_safe_update_source) echo "Для безопасного обновления используется ${CONFIG_FILE}." ;;
    ru:notice_use_env) echo "Передайте --use-env, чтобы переустановить из .env." ;;
    ru:notice_override) echo "Обнаружен существующий timer override:" ;;
    ru:notice_override_runtime) echo "Runtime-интервал может управляться этим override." ;;
    ru:controlled_by_override) echo "управляется systemd override" ;;
    ru:default) echo "по умолчанию" ;;
    ru:existing_timer) echo "существующий systemd timer" ;;
    ru:systemd_override) echo "systemd override" ;;
    ru:timer_not_enabled_flag) echo "Таймер не был включён (--no-enable-timer)." ;;
    ru:installed) echo "Установлено." ;;
    ru:installed_validation_failed) echo "Установлено, но validate завершился с ошибкой." ;;
    ru:installed_incomplete) echo "Установлено, но конфигурация неполная." ;;
    ru:timer_not_enabled) echo "Таймер не был включён." ;;
    ru:run) echo "Выполните:" ;;
    ru:config) echo "Конфиг" ;;
    ru:preserved_config) echo "сохраняется, не перезаписывается" ;;
    ru:command) echo "Команда" ;;
    ru:try) echo "Попробуйте:" ;;
    ru:use_env_missing) echo "ОШИБКА: передан --use-env, но ${ENV_FILE} не существует" ;;
    en:dry_run|*:dry_run) echo "Dry run only. Would install:" ;;
    en:detected|*:detected) echo "Detected/configured:" ;;
    en:config_source|*:config_source) echo "Config source" ;;
    en:timer_interval|*:timer_interval) echo "Timer interval" ;;
    en:timer_source|*:timer_source) echo "Timer source" ;;
    en:timer_override|*:timer_override) echo "Timer override" ;;
    en:timer_enable|*:timer_enable) echo "Timer enable" ;;
    en:yes|*:yes) echo "yes" ;;
    en:no|*:no) echo "no" ;;
    en:none|*:none) echo "none" ;;
    en:auto_detect|*:auto_detect) echo "auto-detect" ;;
    en:run_installer|*:run_installer) echo "Run installer with these values? [y/N]" ;;
    en:cancelled|*:cancelled) echo "Cancelled." ;;
    en:run_as_root|*:run_as_root) echo "ERROR: run as root" ;;
    en:backup|*:backup) echo "Backup" ;;
    en:notice_both|*:notice_both) echo "Notice: both .env and ${CONFIG_FILE} exist." ;;
    en:notice_env_source|*:notice_env_source) echo "Using .env as explicit install source." ;;
    en:notice_config_overwrite|*:notice_config_overwrite) echo "Existing installed config will be overwritten after backup." ;;
    en:notice_env_ignored|*:notice_env_ignored) echo ".env exists, but installed config exists too." ;;
    en:notice_safe_update_source|*:notice_safe_update_source) echo "Using ${CONFIG_FILE} for safe update." ;;
    en:notice_use_env|*:notice_use_env) echo "Pass --use-env to reinstall from .env." ;;
    en:notice_override|*:notice_override) echo "Notice: existing timer override found:" ;;
    en:notice_override_runtime|*:notice_override_runtime) echo "Runtime interval may be controlled by this override." ;;
    en:controlled_by_override|*:controlled_by_override) echo "controlled by systemd override" ;;
    en:default|*:default) echo "default" ;;
    en:existing_timer|*:existing_timer) echo "existing systemd timer" ;;
    en:systemd_override|*:systemd_override) echo "systemd override" ;;
    en:timer_not_enabled_flag|*:timer_not_enabled_flag) echo "Timer was not enabled (--no-enable-timer)." ;;
    en:installed|*:installed) echo "Installed." ;;
    en:installed_validation_failed|*:installed_validation_failed) echo "Installed, but validation failed." ;;
    en:installed_incomplete|*:installed_incomplete) echo "Installed, but configuration is incomplete." ;;
    en:timer_not_enabled|*:timer_not_enabled) echo "The timer was not enabled." ;;
    en:run|*:run) echo "Run:" ;;
    en:config|*:config) echo "Config" ;;
    en:preserved_config|*:preserved_config) echo "preserved, not rewritten" ;;
    en:command|*:command) echo "Command" ;;
    en:try|*:try) echo "Try:" ;;
    en:use_env_missing|*:use_env_missing) echo "ERROR: --use-env was passed, but ${ENV_FILE} does not exist" ;;
    *) echo "$key" ;;
  esac
}

yes_no() {
  if [[ "$1" == "1" ]]; then
    msg yes
  else
    msg no
  fi
}

timer_source_label() {
  case "$1" in
    default) msg default ;;
    "existing systemd timer") msg existing_timer ;;
    "systemd override") msg systemd_override ;;
    *) echo "$1" ;;
  esac
}

config_source_label() {
  case "$1" in
    auto-detect) msg auto_detect ;;
    *) echo "$1" ;;
  esac
}

detect_defaults() {
  local route first_addr detected_prefix
  route="$(ip -6 route show default 2>/dev/null | head -n1 || true)"

  [[ -n "$IFACE" ]] || IFACE="$(awk '{for (i=1; i<=NF; i++) if ($i=="dev") {print $(i+1); exit}}' <<< "$route")"
  [[ -n "$GATEWAY" ]] || GATEWAY="$(awk '{for (i=1; i<=NF; i++) if ($i=="via") {print $(i+1); exit}}' <<< "$route")"

  if [[ -z "$PREFIX" && -n "$IFACE" ]]; then
    first_addr="$(ip -o -6 addr show dev "$IFACE" scope global 2>/dev/null | awk '{print $4; exit}' || true)"
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

detect_existing_timer_interval() {
  local value=""

  if [[ -f "${TIMER_FILE}" ]]; then
    value="$(
      awk -F= '
        $1 == "OnUnitActiveSec" && $2 != "" {
          v=$2
        }
        END {
          if (v != "") print v
        }
      ' "${TIMER_FILE}"
    )"
  fi

  if [[ -n "$value" ]]; then
    echo "$value"
    return 0
  fi

  echo ""
}

select_timer_interval() {
  if [[ -n "${INTERVAL:-}" ]]; then
    TIMER_SOURCE="${CONFIG_SOURCE}"
  elif [[ -f "${TIMER_OVERRIDE_FILE}" ]]; then
    INTERVAL="$(detect_existing_timer_interval)"
    INTERVAL="${INTERVAL:-10min}"
    TIMER_SOURCE="systemd override"
  elif [[ -f "${TIMER_FILE}" ]]; then
    INTERVAL="$(detect_existing_timer_interval)"
    INTERVAL="${INTERVAL:-10min}"
    TIMER_SOURCE="existing systemd timer"
  else
    INTERVAL="10min"
    TIMER_SOURCE="default"
  fi
}

warn_env_overrides_config() {
  if [[ "${ENV_OVERRIDES_CONFIG}" == "1" ]]; then
    echo "$(msg notice_both)"
    echo "$(msg notice_env_source)"
    echo "$(msg notice_config_overwrite)"
  fi
}

warn_env_ignored_for_safe_update() {
  if [[ "${ENV_IGNORED_FOR_SAFE_UPDATE}" == "1" ]]; then
    echo "$(msg notice_env_ignored)"
    echo "$(msg notice_safe_update_source)"
    echo "$(msg notice_use_env)"
  fi
}

warn_timer_override() {
  if [[ -f "${TIMER_OVERRIDE_FILE}" ]]; then
    echo "$(msg notice_override)"
    echo "  ${TIMER_OVERRIDE_FILE}"
    echo "$(msg notice_override_runtime)"
  fi
}

print_detected() {
  echo "$(msg detected)"
  echo "  $(msg config_source): $(config_source_label "${CONFIG_SOURCE}")"
  echo "  IFACE=${IFACE}"
  echo "  GATEWAY=${GATEWAY}"
  echo "  PREFIX=${PREFIX}"
  echo "  KEEP_ADDRS=${KEEP_ADDRS}"
  echo "  LANGUAGE=${LANGUAGE}"
  echo "  GRACE_SECONDS=${GRACE_SECONDS}"
  echo "  MAX_OLD_ADDRS=${MAX_OLD_ADDRS}"
  echo "  HEALTHCHECK_MODE=${HEALTHCHECK_MODE}"
}

print_timer_summary() {
  local interval_display
  interval_display="${INTERVAL}"
  if [[ "${TIMER_SOURCE}" == "systemd override" ]]; then
    interval_display="$(msg controlled_by_override)"
  fi

  echo "$(msg timer_interval): ${interval_display}"
  echo "$(msg timer_source): $(timer_source_label "${TIMER_SOURCE}")"
  if [[ -f "${TIMER_OVERRIDE_FILE}" ]]; then
    echo "$(msg timer_override): ${TIMER_OVERRIDE_FILE}"
  else
    echo "$(msg timer_override): $(msg none)"
  fi
}

confirm_detected() {
  if [[ "${ASSUME_YES:-0}" == "1" ]]; then
    return 0
  fi

  print_detected
  echo "  INTERVAL=${INTERVAL}"
  echo
  print_timer_summary
  echo
  echo "$(msg run_installer)"
  read -r answer
  [[ "$answer" == "y" || "$answer" == "Y" || "$answer" == "yes" || "$answer" == "YES" ]]
}

backup_if_exists() {
  local file="$1"
  local ts
  ts="$(date +%F-%H%M%S)"
  if [[ -e "$file" || -L "$file" ]]; then
    cp -a "$file" "${file}.bak.${ts}"
    echo "$(msg backup): ${file}.bak.${ts}"
  fi
}

detect_defaults
select_timer_interval

CONFIG_COMPLETE=1
[[ -n "$PREFIX" ]] || CONFIG_COMPLETE=0
[[ -n "$IFACE" ]] || CONFIG_COMPLETE=0
[[ -n "$GATEWAY" ]] || CONFIG_COMPLETE=0
[[ -n "$KEEP_ADDRS" ]] || CONFIG_COMPLETE=0

CONFIG_WRITE=1
if [[ "${CONFIG_SOURCE}" == "${CONFIG_FILE}" && "${USE_ENV}" != "1" ]]; then
  CONFIG_WRITE=0
fi

if [[ "$DRY_RUN" == "1" ]]; then
  echo "$(msg dry_run)"
  echo "  /usr/local/bin/ipv6-rotate"
  echo "  /usr/local/bin/ipv6-rotate-cli.py"
  if [[ "${CONFIG_WRITE}" == "1" ]]; then
    echo "  ${CONFIG_FILE}"
  else
    echo "  ${CONFIG_FILE} ($(msg preserved_config))"
  fi
  echo "  /etc/systemd/system/ipv6-rotate.service"
  echo "  ${TIMER_FILE}"
  echo
  warn_env_ignored_for_safe_update
  [[ "${ENV_IGNORED_FOR_SAFE_UPDATE}" == "1" ]] && echo
  warn_env_overrides_config
  [[ "${ENV_OVERRIDES_CONFIG}" == "1" ]] && echo
  print_detected
  echo
  print_timer_summary
  echo "$(msg timer_enable): $(yes_no "${ENABLE_TIMER}")"
  warn_timer_override
  exit 0
fi

warn_env_ignored_for_safe_update
[[ "${ENV_IGNORED_FOR_SAFE_UPDATE}" == "1" ]] && echo
warn_env_overrides_config
[[ "${ENV_OVERRIDES_CONFIG}" == "1" ]] && echo
warn_timer_override
[[ -f "${TIMER_OVERRIDE_FILE}" ]] && echo

confirm_detected || {
  echo "$(msg cancelled)"
  exit 1
}

if [[ "${EUID}" -ne 0 ]]; then
  echo "$(msg run_as_root)"
  exit 1
fi

backup_if_exists /usr/local/bin/ipv6-rotate
backup_if_exists /usr/local/bin/ipv6-rotate.sh
backup_if_exists /usr/local/bin/ipv6-rotate-cli.py
if [[ "${CONFIG_WRITE}" == "1" ]]; then
  backup_if_exists "$CONFIG_FILE"
fi
backup_if_exists /etc/systemd/system/ipv6-rotate.service
backup_if_exists "$TIMER_FILE"

install -m 0755 "${ROOT_DIR}/ipv6-rotate" /usr/local/bin/ipv6-rotate
install -m 0644 "${ROOT_DIR}/cli.py" /usr/local/bin/ipv6-rotate-cli.py
ln -sf /usr/local/bin/ipv6-rotate /usr/local/bin/ipv6-rotate.sh

if [[ "${CONFIG_WRITE}" == "1" ]]; then
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
fi

install -m 0644 "${ROOT_DIR}/ipv6-rotate.service" /etc/systemd/system/ipv6-rotate.service
sed "s|\${INTERVAL}|${INTERVAL}|g" "${ROOT_DIR}/ipv6-rotate.timer" > "$TIMER_FILE"

systemctl daemon-reload
warn_timer_override

echo
if [[ "$CONFIG_COMPLETE" == "1" ]]; then
  if /usr/local/bin/ipv6-rotate validate; then
    if [[ "$ENABLE_TIMER" == "1" ]]; then
      systemctl enable --now ipv6-rotate.timer
    else
      echo "$(msg timer_not_enabled_flag)"
    fi
    echo "$(msg installed)"
  else
    echo "$(msg installed_validation_failed)"
    echo "$(msg timer_not_enabled)"
    echo
    echo "$(msg run)"
    echo "  ipv6-rotate setup"
    echo "  ipv6-rotate validate"
    echo "  systemctl enable --now ipv6-rotate.timer"
  fi
else
  echo "$(msg installed_incomplete)"
  echo "$(msg timer_not_enabled)"
  echo
  echo "$(msg run)"
  echo "  ipv6-rotate setup"
  echo "  ipv6-rotate validate"
  echo "  systemctl enable --now ipv6-rotate.timer"
fi
if [[ "${CONFIG_WRITE}" == "1" ]]; then
  echo "$(msg config): ${CONFIG_FILE}"
else
  echo "$(msg config): ${CONFIG_FILE} ($(msg preserved_config))"
fi
echo "$(msg command): /usr/local/bin/ipv6-rotate"
echo
echo "$(msg try)"
echo "  ipv6-rotate status"
echo "  ipv6-rotate dry-run"
echo "  ipv6-rotate rotate"
echo "  ipv6-rotate doctor"
echo "  ipv6-rotate menu"
