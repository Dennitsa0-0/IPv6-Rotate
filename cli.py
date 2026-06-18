#!/usr/bin/env python3
import argparse
import contextlib
import datetime as dt
import io
import ipaddress
import json
import locale
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import textwrap
from pathlib import Path


CONFIG_FILE = Path(os.environ.get("CONFIG_FILE", "/etc/default/ipv6-rotate"))
STATE_DIR = Path(os.environ.get("STATE_DIR", "/var/lib/ipv6-rotate"))
STATE_FILE = Path(os.environ.get("STATE_FILE", str(STATE_DIR / "state.json")))
LOCK_FILE = Path(os.environ.get("LOCK_FILE", "/run/ipv6-rotate.lock"))
VERSION = "0.4.1"
HEALTHCHECK_MODES = {"basic", "normal", "strict", "paranoid"}
TIMER_OVERRIDE_DIR = Path(os.environ.get("TIMER_OVERRIDE_DIR", "/etc/systemd/system/ipv6-rotate.timer.d"))
TIMER_OVERRIDE_FILE = TIMER_OVERRIDE_DIR / "override.conf"
LANGUAGES = {"auto", "en", "ru"}
UI_INDENT = "    "
COMMAND_GROUPS = [
    ("Rotation", [
        ("rotate", "add a new IPv6 and switch default route src"),
        ("dry-run", "preview rotation without changing the network"),
        ("rollback", "switch default route src back to a previous IPv6"),
        ("cleanup", "remove old rotated IPv6 addresses after the grace period"),
    ]),
    ("Status and diagnostics", [
        ("status", "show current status"),
        ("watch", "refresh status in a live terminal view"),
        ("doctor", "run operational diagnostics"),
        ("safe-check", "verify that it is safe to leave the host unattended"),
        ("healthcheck", "run a route healthcheck"),
        ("validate", "validate config and host requirements"),
        ("test", "run healthcheck for the current route src"),
        ("self-test", "run internal CLI checks"),
        ("addresses", "show IPv6 addresses assigned to the interface"),
        ("history", "show rotation history from state"),
        ("logs", "show service logs"),
        ("timer", "show or manage the systemd timer"),
    ]),
    ("Configuration", [
        ("detect", "detect IPv6 configuration"),
        ("setup", "interactive configuration setup"),
        ("config", "show effective configuration"),
        ("edit-config", "open the config file in EDITOR"),
        ("language", "show or set CLI language"),
        ("notify-test", "send a test webhook notification"),
    ]),
    ("Service", [
        ("enable", "enable and start the systemd timer"),
        ("disable", "disable and stop the systemd timer"),
        ("restart-timer", "restart the systemd timer"),
        ("emergency", "print emergency recovery guidance"),
        ("restore-route", "restore default route src"),
        ("print-rescue", "print manual rescue commands"),
        ("menu", "open interactive menu"),
        ("version", "show version and file paths"),
        ("purge", "delete config, state, and logs"),
        ("uninstall", "remove installed files"),
    ]),
]
COMMAND_DESCRIPTIONS = {
    name: description
    for _, commands in COMMAND_GROUPS
    for name, description in commands
}
COMMAND_GROUPS_RU = [
    ("Ротация", [
        ("rotate", "добавить новый IPv6 и переключить route src"),
        ("dry-run", "показать ротацию без изменения сети"),
        ("rollback", "вернуть route src на предыдущий IPv6"),
        ("cleanup", "удалить старые IPv6 после grace period"),
    ]),
    ("Статус и диагностика", [
        ("status", "показать текущий статус"),
        ("watch", "обновлять статус в live-режиме терминала"),
        ("doctor", "запустить диагностику"),
        ("safe-check", "проверить, что хост можно оставить без присмотра"),
        ("healthcheck", "проверить маршрут"),
        ("validate", "проверить конфиг и требования хоста"),
        ("test", "запустить healthcheck для текущего route src"),
        ("self-test", "запустить внутренние проверки CLI"),
        ("addresses", "показать IPv6-адреса интерфейса"),
        ("history", "показать историю ротаций из state"),
        ("logs", "показать логи сервиса"),
        ("timer", "показать или настроить systemd timer"),
    ]),
    ("Конфигурация", [
        ("detect", "найти IPv6-конфигурацию"),
        ("setup", "интерактивная настройка"),
        ("config", "показать эффективную конфигурацию"),
        ("edit-config", "открыть файл конфига в EDITOR"),
        ("language", "показать или изменить язык CLI"),
        ("notify-test", "отправить тестовое webhook-уведомление"),
    ]),
    ("Сервис", [
        ("enable", "включить и запустить systemd timer"),
        ("disable", "отключить и остановить systemd timer"),
        ("restart-timer", "перезапустить systemd timer"),
        ("emergency", "показать команды аварийного восстановления"),
        ("restore-route", "восстановить route src"),
        ("print-rescue", "показать ручные rescue-команды"),
        ("menu", "открыть интерактивное меню"),
        ("version", "показать версию и пути файлов"),
        ("purge", "удалить конфиг, state и логи"),
        ("uninstall", "удалить установленные файлы"),
    ]),
]
COMMAND_DESCRIPTIONS_RU = {
    name: description
    for _, commands in COMMAND_GROUPS_RU
    for name, description in commands
}


MESSAGES = {
    "en": {
        "active": "active",
        "addresses_title": "IPv6 Addresses",
        "all_present": "all present",
        "auto": "auto",
        "cancel": "Cancel",
        "cancelled": "Cancelled.",
        "change_values": "Change values manually",
        "check": "Check",
        "choose_option": "Choose an option: ",
        "config_title": "IPv6 Rotate Config",
        "continue": "Continue? [y/N] ",
        "current": "current",
        "current_route_src": "Current route src",
        "default_route": "Default route",
        "details": "Details",
        "detected_title": "Detected IPv6 configuration",
        "doctor_title": "Doctor",
        "enabled": "Enabled",
        "external_check": "External check",
        "external_ipv6": "External IPv6",
        "gateway": "Gateway",
        "gateway_ping": "Gateway ping",
        "grace_seconds": "Grace seconds",
        "health": "Health",
        "healthcheck": "Healthcheck",
        "healthcheck_mode": "Healthcheck mode",
        "interface": "Interface",
        "keep_address": "Keep address",
        "keep_addresses": "Keep addresses",
        "language": "Language",
        "last_error": "Last error",
        "last_rotation": "Last rotation",
        "last_trigger": "Last trigger",
        "log_file": "Log file",
        "manual_prompt": "Leave empty to keep current value.",
        "missing": "missing",
        "next_rotation": "Next rotation",
        "no_addresses": "No global IPv6 addresses from {network} on {iface}",
        "not_set": "not set",
        "old_kept_addresses": "Old kept addresses",
        "press_enter": "\nPress Enter to continue... ",
        "prefix": "Prefix",
        "public_ipv6": "Public IPv6",
        "result": "Result",
        "route_src": "Route src",
        "run_validation": "Run validation now? [Y/n] ",
        "save_config": "Yes, save config",
        "setup_saved": "Saved configuration to {path}",
        "show_addresses": "Show detected IPv6 addresses",
        "state_file": "State file",
        "status": "Status",
        "status_title": "IPv6 Rotate Status",
        "timer": "Timer",
        "timer_active": "Timer active",
        "timer_title": "IPv6 Rotate Timer",
        "unknown": "unknown",
        "unknown_option": "Unknown option: {choice}",
        "use_config": "Use this configuration?",
        "validation_title": "Validation",
        "webhook": "Webhook",
    "cli_description": "Safe transactional IPv6 source-address rotator for Linux servers with systemd.",
    "cli_path": "CLI path",
        "commands": "Commands",
        "common_commands": "Common commands",
        "config_file": "Config file",
        "dry_run_title": "Dry run",
        "global_options": "Global options",
        "grace_period": "Grace period",
        "help": "Help",
        "inactive": "inactive",
        "interval": "Interval",
        "max_old_addresses": "Max old addresses",
        "next_commands": "Next commands",
        "none": "none",
        "old_addresses": "Old addresses",
        "resolved": "Resolved",
        "rotation_interval": "Rotation interval",
        "run": "Run",
        "timer_enabled": "Timer enabled",
        "usage": "usage",
        "would_add": "Would add",
        "would_deprecate": "Would deprecate",
        "would_keep": "Would keep",
        "would_remove_after_grace": "Would remove after grace period",
        "would_set_default_route": "Would set default route",
    },
    "ru": {},
}

MESSAGES["en"].update({
    "action": "Action",
    "address_lifetime": "Lifetime",
    "address_role": "Role",
    "address_readiness_wait": "address readiness wait",
    "already_running": "Another ipv6-rotate process is already running",
    "all_present": "all present",
    "cancelled": "Cancelled.",
    "clean_error": "clean error",
    "cleanup_confirm": "This will delete ipv6-rotate config, state, and log files.",
    "cleanup_menu_confirm": "This may remove old rotated IPv6 addresses.\nStatic KEEP_ADDRS will not be removed.",
    "command": "Command",
    "command_help_check": "command help",
    "command_help_detail": "help doctor",
    "config": "Config",
    "config_incomplete": "Config is incomplete: {error}",
    "config_parse": "config parse",
    "could_not_generate_ip": "Could not generate a non-reserved IPv6 address",
    "curl_not_installed": "curl is not installed",
    "detect_gateway_missing": "GATEWAY is not set and could not be auto-detected",
    "detect_iface_missing": "IFACE is not set and could not be auto-detected",
    "detect_prefix_missing": "PREFIX is not set and could not be auto-detected",
    "default_route": "Default route",
    "emergency_title": "Emergency rescue commands",
    "failed_notification": "FAIL: test notification was not sent",
    "gateway_reachable": "Gateway reachable",
    "invalid_command": "Unknown command: {command}",
    "invalid_command_help_check": "invalid command help",
    "invalid_prefix": "invalid PREFIX",
    "interval_empty": "Interval is empty",
    "interval_invalid": "Interval must look like 30s, 7min, 1h, or a number of seconds",
    "interface_exists": "Interface exists",
    "language_invalid": "LANGUAGE must be one of: auto, en, ru",
    "language_menu_title": "CLI language",
    "language_saved": "Language saved: {language}",
    "menu_disable_timer_confirm": "This will disable ipv6-rotate.timer.",
    "menu_restart_timer_confirm": "This will restart ipv6-rotate.timer.",
    "rollback_menu_confirm": "This will change default IPv6 route src to the previous address from state.",
    "rotate_menu_confirm": "This will add a new IPv6 address and change default IPv6 route src.",
    "log_source_missing": "No journalctl and no log file: {path}",
    "matched": "matched",
    "network_detected": "Network detected",
    "no_history": "No rotation history in {path}",
    "no_rescue_ipv6": "No rescue IPv6 found in state or KEEP_ADDRS",
    "no_route_source": "No route source available",
    "not_found": "not found",
    "not_root": "not root",
    "notify_sent": "OK: test notification sent",
    "prefix_format": "Prefix format",
    "ping_checks": "Ping checks",
    "prefix_missing": "PREFIX is not set, example: PREFIX='2001:db8:abcd:1234'",
    "positional_arguments": "positional arguments",
    "arg_timer_interval": "interval for timer set, for example 7min",
    "arg_max_old": "maximum old rotated addresses to keep",
    "arg_rollback_ip": "specific IPv6 address to use as default route src",
    "arg_restore_address": "add rollback target back to IFACE if it is missing",
    "arg_restore_route_ip": "IPv6 address to use as default route src",
    "arg_purge_yes": "delete config/state/logs without asking",
    "public_ipv6_unavailable": "public IPv6 unavailable",
    "purge_removed": "Removed {path}",
    "removed": "Removed",
    "rollback_no_previous": "No previous/current IPv6 in {path}",
    "restore_address_failed": "failed to restore IPv6 address {target}",
    "rollback_not_assigned": "Rollback target is not assigned to {iface}: {target}. Use --restore-address to add it back.",
    "rollback_outside_prefix": "Rollback target is outside PREFIX: {target}",
    "root_check": "Running as root",
    "rotation_history_title": "Rotation history",
    "rotated_prefix_addrs": "Rotated prefix addrs",
    "route_src_match": "Route src match",
    "run_as_root": "ERROR: run as root",
    "safe_check_title": "Safe check",
    "safe_result": "SAFE",
    "self_test_title": "Self Test",
    "setup_validation_failed": "Validation failed with exit code {code}.",
    "state_read": "state read",
    "table_cell_wrapping": "table cell wrapping",
    "table_rendering": "table rendering",
    "test_notification": "ipv6-rotate test notification from {host}",
    "timer_action_done": "Timer action completed",
    "time": "Time",
    "unavailable": "unavailable",
    "unsafe_result": "UNSAFE",
    "usage_config_set": "Usage: ipv6-rotate config set <key> <value>",
    "usage_timer_set": "Usage: ipv6-rotate timer set 7min",
    "url_checks": "URL checks",
    "unknown_config_key": "Unknown config key: {key}",
    "mode_invalid": "HEALTHCHECK_MODE must be one of: basic, normal, strict, paranoid",
    "healthcheck_mode_invalid": "Mode must be one of: basic, normal, strict, paranoid",
    "keep_empty": "KEEP_ADDRS is empty. Run ipv6-rotate setup or set KEEP_ADDRS explicitly.",
    "keep_assigned": "KEEP_ADDRS assigned",
    "keep_in_prefix": "KEEP_ADDRS in prefix",
    "external_ipv6_reachable": "External IPv6 reachable",
    "last_rotation_success": "Last rotation success",
    "next_rotation_scheduled": "Next rotation scheduled",
    "old_addresses_count_ok": "Old addresses count acceptable",
    "route_src_matches_public": "route src matches public IPv6",
    "systemd_timer_installed": "systemd timer installed",
    "validate_installer_only": "{dep} installer-only",
    "validate_installed": "{dep} installed",
    "validate_recommended": "{dep} recommended",
    "version": "Version",
    "version_title": "IPv6 Rotate Version",
    "webhook_not_set": "WEBHOOK_URL is not set",
})

MESSAGES["ru"].update({
    "action": "Действие",
    "active": "активен",
    "address_lifetime": "Lifetime",
    "address_readiness_wait": "ожидание готовности адреса",
    "address_role": "Роль",
    "addresses_title": "IPv6-адреса",
    "already_running": "Другой процесс ipv6-rotate уже запущен",
    "all_present": "все назначены",
    "arg_max_old": "максимум старых ротированных адресов",
    "arg_purge_yes": "удалить конфиг/state/логи без вопроса",
    "arg_restore_address": "добавить rollback target обратно на IFACE, если его нет",
    "arg_restore_route_ip": "IPv6-адрес для default route src",
    "arg_rollback_ip": "конкретный IPv6-адрес для default route src",
    "arg_timer_interval": "интервал для timer set, например 7min",
    "auto": "авто",
    "cancel": "Отмена",
    "cancelled": "Отменено.",
    "change_values": "Изменить вручную",
    "check": "Проверка",
    "choose_option": "Выберите пункт: ",
    "clean_error": "чистая ошибка",
    "cleanup_confirm": "Будут удалены конфиг, state и логи ipv6-rotate.",
    "cleanup_menu_confirm": "Могут быть удалены старые ротированные IPv6-адреса.\nСтатические KEEP_ADDRS не будут удалены.",
    "cli_description": "Безопасная транзакционная ротация исходного IPv6-адреса для Linux-серверов с systemd.",
    "cli_path": "Путь CLI",
    "command": "Команда",
    "command_help_check": "справка команды",
    "command_help_detail": "help doctor",
    "commands": "Команды",
    "common_commands": "Основные команды",
    "config": "Конфиг",
    "config_file": "Файл конфига",
    "config_incomplete": "Конфиг неполный: {error}",
    "config_parse": "разбор конфига",
    "config_title": "Конфигурация IPv6 Rotate",
    "continue": "Продолжить? [y/N] ",
    "could_not_generate_ip": "Не удалось сгенерировать нерезервный IPv6-адрес",
    "curl_not_installed": "curl не установлен",
    "current": "текущий",
    "current_route_src": "Текущий route src",
    "default_route": "Default route",
    "details": "Детали",
    "detect_gateway_missing": "GATEWAY не задан и не был найден автоматически",
    "detect_iface_missing": "IFACE не задан и не был найден автоматически",
    "detect_prefix_missing": "PREFIX не задан и не был найден автоматически",
    "detected_title": "Найдена IPv6-конфигурация",
    "doctor_title": "Диагностика",
    "dry_run_title": "Пробный запуск",
    "emergency_title": "Команды аварийного восстановления",
    "enabled": "Включён",
    "external_check": "Внешняя проверка",
    "external_ipv6": "Внешний IPv6",
    "external_ipv6_reachable": "Внешний IPv6 доступен",
    "failed_notification": "FAIL: тестовое уведомление не отправлено",
    "gateway": "Шлюз",
    "gateway_ping": "Ping gateway",
    "gateway_reachable": "Gateway доступен",
    "global_options": "Глобальные опции",
    "grace_period": "Grace period",
    "grace_seconds": "Grace seconds",
    "health": "Состояние",
    "healthcheck": "Проверка связи",
    "healthcheck_mode": "Режим проверки",
    "healthcheck_mode_invalid": "Режим должен быть одним из: basic, normal, strict, paranoid",
    "help": "Справка",
    "inactive": "неактивен",
    "interface": "Интерфейс",
    "interface_exists": "Интерфейс существует",
    "interval": "Интервал",
    "interval_empty": "Интервал пустой",
    "interval_invalid": "Интервал должен выглядеть как 30s, 7min, 1h или число секунд",
    "invalid_command": "Неизвестная команда: {command}",
    "invalid_command_help_check": "справка неизвестной команды",
    "invalid_prefix": "некорректный PREFIX",
    "keep_address": "Не удалять адрес",
    "keep_addresses": "Не удалять адреса",
    "keep_assigned": "KEEP_ADDRS назначены",
    "keep_empty": "KEEP_ADDRS пустой. Запустите ipv6-rotate setup или задайте KEEP_ADDRS явно.",
    "keep_in_prefix": "KEEP_ADDRS в префиксе",
    "language": "Язык",
    "language_invalid": "LANGUAGE должен быть одним из: auto, en, ru",
    "language_menu_title": "Язык CLI",
    "language_saved": "Язык сохранён: {language}",
    "last_error": "Последняя ошибка",
    "last_rotation": "Последняя ротация",
    "last_rotation_success": "Последняя ротация успешна",
    "last_trigger": "Последний запуск",
    "log_file": "Файл лога",
    "log_source_missing": "Нет journalctl и нет файла лога: {path}",
    "manual_prompt": "Оставьте пустым, чтобы сохранить текущее значение.",
    "matched": "совпало",
    "max_old_addresses": "Максимум старых адресов",
    "menu_disable_timer_confirm": "ipv6-rotate.timer будет отключён.",
    "menu_restart_timer_confirm": "ipv6-rotate.timer будет перезапущен.",
    "missing": "не задано",
    "mode_invalid": "HEALTHCHECK_MODE должен быть одним из: basic, normal, strict, paranoid",
    "network_detected": "Сеть найдена",
    "next_commands": "Следующие команды",
    "next_rotation": "Следующая ротация",
    "next_rotation_scheduled": "Следующая ротация запланирована",
    "no_addresses": "На {iface} нет глобальных IPv6-адресов из {network}",
    "no_history": "Нет истории ротаций в {path}",
    "no_rescue_ipv6": "Нет rescue IPv6 в state или KEEP_ADDRS",
    "no_route_source": "Нет доступного route src",
    "none": "нет",
    "not_found": "не найден",
    "not_root": "не root",
    "not_set": "не задан",
    "notify_sent": "OK: тестовое уведомление отправлено",
    "old_addresses": "Старые адреса",
    "old_addresses_count_ok": "Количество старых адресов допустимо",
    "old_kept_addresses": "Старые сохранённые адреса",
    "ping_checks": "Ping-проверки",
    "positional_arguments": "аргументы",
    "prefix": "Префикс",
    "prefix_format": "Формат префикса",
    "prefix_missing": "PREFIX не задан, пример: PREFIX='2001:db8:abcd:1234'",
    "press_enter": "\nНажмите Enter, чтобы продолжить... ",
    "public_ipv6": "Публичный IPv6",
    "public_ipv6_unavailable": "публичный IPv6 недоступен",
    "purge_removed": "Удалено: {path}",
    "removed": "Удалено",
    "resolved": "Разрешённый язык",
    "restore_address_failed": "не удалось восстановить IPv6-адрес {target}",
    "result": "Результат",
    "rollback_menu_confirm": "Default IPv6 route src будет переключён на предыдущий адрес из state.",
    "rollback_no_previous": "Нет предыдущего/текущего IPv6 в {path}",
    "rollback_not_assigned": "Rollback target не назначен на {iface}: {target}. Используйте --restore-address, чтобы добавить его обратно.",
    "rollback_outside_prefix": "Rollback target вне PREFIX: {target}",
    "root_check": "Запуск от root",
    "rotate_menu_confirm": "Будет добавлен новый IPv6-адрес и изменён default IPv6 route src.",
    "rotated_prefix_addrs": "Адреса ротируемого префикса",
    "rotation_history_title": "История ротаций",
    "rotation_interval": "Интервал ротации",
    "route_src": "Route src",
    "route_src_match": "Совпадение route src",
    "route_src_matches_public": "route src совпадает с публичным IPv6",
    "run": "Выполните",
    "run_as_root": "ОШИБКА: запустите от root",
    "run_validation": "Запустить проверку сейчас? [Y/n] ",
    "safe_check_title": "Безопасная проверка",
    "safe_result": "БЕЗОПАСНО",
    "save_config": "Да, сохранить",
    "self_test_title": "Self Test",
    "setup_saved": "Конфигурация сохранена в {path}",
    "setup_validation_failed": "Проверка завершилась с кодом {code}.",
    "show_addresses": "Показать найденные IPv6-адреса",
    "state_file": "Файл состояния",
    "state_read": "чтение state",
    "status": "Статус",
    "status_title": "Статус IPv6 Rotate",
    "systemd_timer_installed": "systemd timer установлен",
    "table_cell_wrapping": "перенос ячейки таблицы",
    "table_rendering": "отрисовка таблицы",
    "test_notification": "тестовое уведомление ipv6-rotate от {host}",
    "time": "Время",
    "timer": "Таймер",
    "timer_action_done": "Действие таймера выполнено",
    "timer_active": "Таймер активен",
    "timer_enabled": "Таймер включён",
    "timer_title": "Таймер IPv6 Rotate",
    "unavailable": "недоступен",
    "unknown": "неизвестно",
    "unknown_config_key": "Неизвестный ключ конфига: {key}",
    "unknown_option": "Неизвестный пункт: {choice}",
    "unsafe_result": "НЕБЕЗОПАСНО",
    "url_checks": "URL-проверки",
    "usage": "использование",
    "usage_config_set": "Использование: ipv6-rotate config set <key> <value>",
    "usage_timer_set": "Использование: ipv6-rotate timer set 7min",
    "use_config": "Использовать эту конфигурацию?",
    "validate_installed": "{dep} установлен",
    "validate_installer_only": "{dep} только для installer",
    "validate_recommended": "{dep} рекомендован",
    "validation_title": "Проверка",
    "version": "Версия",
    "version_title": "Версия IPv6 Rotate",
    "webhook": "Webhook",
    "webhook_not_set": "WEBHOOK_URL не задан",
    "would_add": "Будет добавлен",
    "would_deprecate": "Будут deprecated",
    "would_keep": "Будут сохранены",
    "would_remove_after_grace": "Будут удалены после grace period",
    "would_set_default_route": "Будет установлен default route",
})


def parse_env_file(path):
    values = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        values[key] = value
    return values


def detect_language():
    language = (locale.getlocale()[0] or os.environ.get("LANG", "") or "").lower()
    return "ru" if language.startswith("ru") or ".ru" in language else "en"


def normalize_language(value):
    value = (value or "auto").strip().lower()
    if value not in LANGUAGES:
        return "auto"
    return value


def normalize_healthcheck_mode(value):
    value = (value or "strict").strip().lower()
    return value


def resolve_language(value):
    value = normalize_language(value)
    return detect_language() if value == "auto" else value


def tr(config, key, **kwargs):
    language = resolve_language(getattr(config, "language", "auto"))
    template = MESSAGES.get(language, MESSAGES["en"]).get(key, MESSAGES["en"].get(key, key))
    return template.format(**kwargs) if kwargs else template


def tv(config, value):
    translations = {
        "unknown": tr(config, "unknown"),
        "missing": tr(config, "missing"),
        "not set": tr(config, "not_set"),
        "not found": tr(config, "not_found"),
        "none": tr(config, "none"),
        "active": tr(config, "active"),
        "inactive": tr(config, "inactive"),
        "unavailable": tr(config, "unavailable"),
        "matched": tr(config, "matched"),
        "all present": tr(config, "all_present"),
        "not root": tr(config, "not_root"),
        "invalid PREFIX": tr(config, "invalid_prefix"),
        "public IPv6 unavailable": tr(config, "public_ipv6_unavailable"),
        "no route src": tr(config, "no_route_source"),
    }
    if resolve_language(getattr(config, "language", "auto")) == "ru":
        translations.update({
            "yes": "да",
            "no": "нет",
            "enabled": "включён",
            "disabled": "отключён",
            "success": "успешно",
            "fail": "ошибка",
            "failed": "ошибка",
        })
    return translations.get(value, value)


def kv(config, key, value):
    return (tr(config, key), tv(config, value))


def check_row(config, key, status, details):
    return [tr(config, key), status, tv(config, details)]


class RussianHelpFormatter(argparse.HelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        if prefix is None:
            prefix = "использование: "
        return super().add_usage(usage, actions, groups, prefix)


class Config:
    def __init__(self):
        file_values = parse_env_file(CONFIG_FILE)
        self.file_values = file_values
        self.iface = os.environ.get("IFACE", file_values.get("IFACE", ""))
        self.prefix = os.environ.get("PREFIX", file_values.get("PREFIX", ""))
        self.gateway = os.environ.get("GATEWAY", file_values.get("GATEWAY", ""))
        self.keep_addrs = os.environ.get("KEEP_ADDRS", file_values.get("KEEP_ADDRS", ""))
        self.language = normalize_language(os.environ.get("LANGUAGE", file_values.get("LANGUAGE", "auto")))
        self.grace_seconds = int(os.environ.get("GRACE_SECONDS", file_values.get("GRACE_SECONDS", "1800")))
        self.max_old_addrs = int(os.environ.get("MAX_OLD_ADDRS", file_values.get("MAX_OLD_ADDRS", "10")))
        self.healthcheck_ping6 = os.environ.get(
            "HEALTHCHECK_PING6",
            file_values.get("HEALTHCHECK_PING6", file_values.get("HEALTHCHECK_HOSTS", "2606:4700:4700::1111 2001:4860:4860::8888")),
        )
        self.healthcheck_urls = os.environ.get(
            "HEALTHCHECK_URLS",
            file_values.get("HEALTHCHECK_URLS", file_values.get("HEALTHCHECK_URL", "https://ifconfig.me https://api64.ipify.org")),
        )
        self.healthcheck_mode = normalize_healthcheck_mode(os.environ.get("HEALTHCHECK_MODE", file_values.get("HEALTHCHECK_MODE", "strict")))
        self.webhook_url = os.environ.get("WEBHOOK_URL", file_values.get("WEBHOOK_URL", file_values.get("NOTIFY_WEBHOOK_URL", "")))
        self.log_file = Path(os.environ.get("LOG_FILE", file_values.get("LOG_FILE", "/var/log/ipv6-rotate.log")))

    @property
    def keep_list(self):
        return [normalize_ip(item) for item in self.keep_addrs.split() if item]

    @property
    def ping_hosts(self):
        return [item for item in self.healthcheck_ping6.split() if item]

    @property
    def urls(self):
        return [item for item in self.healthcheck_urls.split() if item]


def run(args, check=False, input_text=None):
    try:
        return subprocess.run(
            args,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )
    except FileNotFoundError:
        if check:
            raise
        return subprocess.CompletedProcess(args, 127, "", f"{args[0]} not found")


def wants_json(args):
    return bool(getattr(args, "json", False))


def wants_table(args):
    return bool(getattr(args, "table", False))


def print_plain_kv(pairs):
    width = max((len(str(key)) for key, _ in pairs), default=0)
    for key, value in pairs:
        print(f"{key + ':':<{width + 1}} {value}")


def print_records_json(records):
    print(json.dumps(records, indent=2, sort_keys=True))


def command_exists(name):
    return shutil.which(name) is not None


def log(config, message):
    line = f"{dt.datetime.now().astimezone().isoformat(timespec='seconds')} {message}"
    print(line, file=sys.stderr)
    if config.log_file:
        config.log_file.parent.mkdir(parents=True, exist_ok=True)
        with config.log_file.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def need_root(config=None):
    config = config or Config()
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        raise SystemExit(tr(config, "run_as_root"))


def usage_error(message):
    print(message, file=sys.stderr)
    raise SystemExit(2)


def normalize_ip(value):
    return ipaddress.ip_address(value.split("/", 1)[0]).compressed


def prefix_network(prefix):
    return ipaddress.ip_network(prefix.rstrip(":") + "::/64", strict=False)


def ip_in_prefix(value, prefix):
    return ipaddress.ip_address(value.split("/", 1)[0]) in prefix_network(prefix)


def require_config(config):
    if not config.prefix:
        usage_error(tr(config, "prefix_missing"))
    if config.healthcheck_mode not in HEALTHCHECK_MODES:
        usage_error(tr(config, "mode_invalid"))
    if not config.keep_list:
        usage_error(tr(config, "keep_empty"))


def default_route():
    result = run(["ip", "-6", "route", "show", "default"])
    return result.stdout.splitlines()[0] if result.stdout.strip() else ""


def field_after(words, marker):
    try:
        return words[words.index(marker) + 1]
    except (ValueError, IndexError):
        return ""


def detect_network(config):
    route = default_route()
    words = route.split()
    if not config.iface:
        config.iface = field_after(words, "dev")
    if not config.gateway:
        config.gateway = field_after(words, "via")
    if not config.iface:
        usage_error(tr(config, "detect_iface_missing"))
    if not config.gateway:
        usage_error(tr(config, "detect_gateway_missing"))


def default_src():
    result = run(["ip", "-6", "route", "get", "2600:1901:0:b2bd::"])
    words = result.stdout.split()
    source = field_after(words, "src")
    return normalize_ip(source) if source else ""


def global_addresses(config):
    result = run(["ip", "-o", "-6", "addr", "show", "dev", config.iface, "scope", "global"])
    addresses = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            addresses.append(parts[3])
    return addresses


def global_address_details(config):
    result = run(["ip", "-o", "-6", "addr", "show", "dev", config.iface, "scope", "global"])
    details = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        cidr = parts[3]
        item = {
            "cidr": cidr,
            "ip": normalize_ip(cidr),
            "deprecated": "deprecated" in parts,
            "tentative": "tentative" in parts,
            "dadfailed": "dadfailed" in parts,
            "dynamic": "dynamic" in parts,
            "temporary": "temporary" in parts or "mngtmpaddr" in parts,
            "valid_lft": field_after(parts, "valid_lft") or "unknown",
            "preferred_lft": field_after(parts, "preferred_lft") or "unknown",
        }
        details.append(item)
    return details


def prefix_from_ip(value):
    ip = ipaddress.ip_address(value.split("/", 1)[0])
    return ":".join(part.lstrip("0") or "0" for part in ip.exploded.split(":")[:4])


def choose_keep_addrs(config, details, route_src):
    if config.keep_addrs:
        return [normalize_ip(item) for item in config.keep_addrs.split() if item]
    if not config.prefix:
        return []

    candidates = [
        item for item in details
        if ip_in_prefix(item["ip"], config.prefix)
        and not item.get("deprecated")
        and not item.get("dynamic")
        and not item.get("temporary")
    ]
    if not candidates:
        candidates = [item for item in details if ip_in_prefix(item["ip"], config.prefix)]
    if not candidates:
        return []

    static_two = normalize_ip(f"{config.prefix}::2")
    for item in candidates:
        if normalize_ip(item["ip"]) == static_two:
            return [static_two]
    if route_src:
        route_src = normalize_ip(route_src)
        for item in candidates:
            if normalize_ip(item["ip"]) == route_src:
                return [route_src]
    if len(candidates) == 1:
        return [normalize_ip(candidates[0]["ip"])]
    return [normalize_ip(candidates[0]["ip"])]


def detect_config(config):
    route = default_route()
    words = route.split()
    if not config.iface:
        config.iface = field_after(words, "dev")
    if not config.gateway:
        config.gateway = field_after(words, "via")
    if not config.iface:
        usage_error(tr(config, "detect_iface_missing"))
    if not config.gateway:
        usage_error(tr(config, "detect_gateway_missing"))

    details = global_address_details(config)
    route_src = default_src()
    if not config.prefix:
        source = route_src or (details[0]["ip"] if details else "")
        if source:
            config.prefix = prefix_from_ip(source)
    if not config.prefix:
        usage_error(tr(config, "detect_prefix_missing"))

    keep = choose_keep_addrs(config, details, route_src)
    if keep and not config.keep_addrs:
        config.keep_addrs = " ".join(keep)

    gateway_ok = False
    if config.iface and config.gateway:
        gateway_ok = gateway_ping_ok(config)

    public_ip = public_ipv6(config)
    external_ok = bool(route_src and public_ip == route_src)
    return {
        "route": route,
        "route_src": route_src,
        "addresses": details,
        "keep": keep,
        "gateway_ok": gateway_ok,
        "public_ipv6": public_ip,
        "external_ok": external_ok,
    }


def address_exists(config, value):
    target = normalize_ip(value)
    return any(normalize_ip(cidr) == target for cidr in global_addresses(config))


def address_detail(config, value):
    target = normalize_ip(value)
    for item in global_address_details(config):
        if normalize_ip(item["ip"]) == target:
            return item
    return None


def wait_for_address_ready(config, value, timeout=10, interval=0.25):
    target = normalize_ip(value)
    deadline = time.monotonic() + timeout
    last_status = "not present"
    while time.monotonic() <= deadline:
        item = address_detail(config, target)
        if item:
            flags = []
            if item.get("tentative"):
                flags.append("tentative")
            if item.get("dadfailed"):
                flags.append("dadfailed")
            if item.get("deprecated"):
                flags.append("deprecated")
            last_status = ", ".join(flags) if flags else "ready"
            if item.get("dadfailed"):
                return f"IPv6 address failed duplicate address detection: {target}"
            if not item.get("tentative"):
                return ""
        time.sleep(interval)
    return f"IPv6 address did not become ready after {timeout}s: {target} ({last_status})"


def generate_ip(config):
    host = ":".join(f"{secrets.randbelow(0x10000):x}" for _ in range(4))
    return normalize_ip(f"{config.prefix}:{host}")


def is_keep_addr(config, value):
    return normalize_ip(value) in set(config.keep_list)


def is_reserved_generated_ip(config, value):
    target = normalize_ip(value)
    reserved = {
        normalize_ip(f"{config.prefix}::"),
        normalize_ip(f"{config.prefix}::1"),
    }
    if config.gateway:
        reserved.add(normalize_ip(config.gateway))
    return target in reserved or is_keep_addr(config, target)


def load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(STATE_FILE.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(STATE_FILE)


def previous_items():
    return load_state().get("previous", [])


def state_update(current, status, message, previous_hint="", deprecated_at=None, deprecated=None):
    state = load_state()
    now = int(time.time())
    now_iso = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    current = normalize_ip(current) if current else ""
    previous_hint = normalize_ip(previous_hint) if previous_hint else ""
    deprecated_at = int(deprecated_at or now)

    previous = []
    seen = set()

    def add_previous(ip, created_at=None, dep_at=None):
        if not ip:
            return
        ip = normalize_ip(ip)
        if ip == current or ip in seen:
            return
        seen.add(ip)
        previous.append({
            "ip": ip,
            "created_at": int(created_at or now),
            "deprecated_at": int(dep_at or deprecated_at),
        })

    for ip in deprecated or []:
        add_previous(ip, now, deprecated_at)
    add_previous(previous_hint, now, deprecated_at)
    add_previous(state.get("current", ""), now, deprecated_at)
    for item in state.get("previous", []):
        add_previous(item.get("ip", ""), item.get("created_at", now), item.get("deprecated_at", deprecated_at))

    state["current"] = current
    state["previous"] = previous
    if status == "success":
        state["last_success"] = now_iso
        state["last_error"] = None
    else:
        state["last_error"] = {"time": now_iso, "message": message}
    state["last_rotation"] = {"status": status, "message": message, "created_at": now}
    save_state(state)


def state_remove_previous(removed):
    removed = normalize_ip(removed)
    state = load_state()
    state["previous"] = [item for item in state.get("previous", []) if normalize_ip(item.get("ip", "::")) != removed]
    save_state(state)


def terminal_width(default=80, minimum=48):
    return max(minimum, shutil.get_terminal_size((default, 20)).columns)


def wrap_cell(value, width):
    width = max(1, int(width))
    lines = str(value).splitlines() or [""]
    wrapped = []
    for line in lines:
        if not line:
            wrapped.append("")
            continue
        wrapped.extend(textwrap.wrap(
            line,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
            replace_whitespace=False,
            drop_whitespace=True,
        ) or [""])
    return wrapped


def fit_widths(natural_widths, min_widths, available):
    widths = list(min_widths)
    budget = max(sum(widths), available)
    extra = budget - sum(widths)
    needs = [max(0, natural_widths[index] - widths[index]) for index in range(len(widths))]
    while extra > 0 and any(needs):
        changed = False
        for index, need in enumerate(needs):
            if need <= 0 or extra <= 0:
                continue
            widths[index] += 1
            needs[index] -= 1
            extra -= 1
            changed = True
        if not changed:
            break
    return widths


def table_line(widths):
    return UI_INDENT + "+" + "+".join("-" * (width + 2) for width in widths) + "+"


def print_table_row(cells, widths):
    wrapped = [wrap_cell(cells[index], widths[index]) for index in range(len(widths))]
    height = max(len(lines) for lines in wrapped)
    for line_index in range(height):
        parts = []
        for index, width in enumerate(widths):
            value = wrapped[index][line_index] if line_index < len(wrapped[index]) else ""
            parts.append(value.ljust(width))
        print(UI_INDENT + "| " + " | ".join(parts) + " |")


def table_kv(title, pairs):
    print()
    print(f"{UI_INDENT}{title}")
    print()
    pairs = [(str(k), str(v)) for k, v in pairs]
    natural_left = max([len(k) for k, _ in pairs] + [5])
    natural_right = max([len(v) for _, v in pairs] + [5])
    available = terminal_width() - len(UI_INDENT) - 7
    left_min = min(max(natural_left, 8), 24)
    right_min = 16
    left, right = fit_widths([natural_left, natural_right], [left_min, right_min], available)

    print(table_line([left, right]))
    for key, value in pairs:
        print_table_row([key, value], [left, right])
    print(table_line([left, right]))
    print()


def table_rows(title, headers, rows):
    print()
    print(f"{UI_INDENT}{title}")
    print()
    headers = [str(item) for item in headers]
    rows = [[str(item) for item in row] for row in rows]
    column_count = len(headers)
    normalized_rows = []
    for row in rows:
        normalized = row[:column_count] + [""] * max(0, column_count - len(row))
        normalized_rows.append(normalized)

    natural = [len(item) for item in headers]
    for row in normalized_rows:
        for index, item in enumerate(row):
            natural[index] = max(natural[index], len(item))

    min_widths = [min(max(len(header), 6), 18) for header in headers]
    available = terminal_width() - len(UI_INDENT) - (3 * column_count + 1)
    widths = fit_widths(natural, min_widths, available)

    print(table_line(widths))
    print_table_row(headers, widths)
    print(table_line(widths))
    for row in normalized_rows:
        print_table_row(row, widths)
    print(table_line(widths))
    print()


def config_values(config):
    return {
        "IFACE": config.iface,
        "PREFIX": config.prefix,
        "GATEWAY": config.gateway,
        "KEEP_ADDRS": config.keep_addrs,
        "LANGUAGE": config.language,
        "GRACE_SECONDS": str(config.grace_seconds),
        "MAX_OLD_ADDRS": str(config.max_old_addrs),
        "HEALTHCHECK_PING6": config.healthcheck_ping6,
        "HEALTHCHECK_URLS": config.healthcheck_urls,
        "HEALTHCHECK_MODE": config.healthcheck_mode,
        "WEBHOOK_URL": config.webhook_url,
        "LOG_FILE": str(config.log_file),
    }


def write_config_file(config):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'{key}="{value}"' for key, value in config_values(config).items()]
    CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def config_set(key, value):
    config = Config()
    normalized = key.strip().lower().replace("-", "_")
    aliases = {
        "iface": "iface",
        "interface": "iface",
        "prefix": "prefix",
        "gateway": "gateway",
        "keep": "keep_addrs",
        "keep_addrs": "keep_addrs",
        "language": "language",
        "grace": "grace_seconds",
        "grace_seconds": "grace_seconds",
        "max_old": "max_old_addrs",
        "max_old_addrs": "max_old_addrs",
        "healthcheck": "healthcheck_mode",
        "healthcheck_mode": "healthcheck_mode",
        "webhook": "webhook_url",
        "webhook_url": "webhook_url",
        "log_file": "log_file",
    }
    if normalized == "interval":
        interval = set_timer_interval(value, config)
        print_plain_kv([kv(config, "rotation_interval", interval), ("Override", str(TIMER_OVERRIDE_FILE))])
        return
    attr = aliases.get(normalized)
    if not attr:
        usage_error(tr(config, "unknown_config_key", key=key))
    if attr == "language":
        value = normalize_language(value)
    if attr == "healthcheck_mode":
        value = normalize_healthcheck_mode(value)
        if value not in HEALTHCHECK_MODES:
            usage_error(tr(config, "mode_invalid"))
    if attr in {"grace_seconds", "max_old_addrs"}:
        value = str(int(value))
    setattr(config, attr, value)
    write_config_file(config)
    print(f"{attr.upper()}={value}")


def render_detected_config(config, detected):
    table_kv(tr(config, "detected_title"), [
        (tr(config, "interface"), config.iface or tr(config, "missing")),
        (tr(config, "gateway"), config.gateway or tr(config, "missing")),
        (tr(config, "prefix"), config.prefix or tr(config, "missing")),
        (tr(config, "keep_address"), config.keep_addrs or tr(config, "missing")),
        (tr(config, "public_ipv6"), detected.get("public_ipv6") or tr(config, "unknown")),
        (tr(config, "gateway_ping"), "OK" if detected.get("gateway_ok") else "WARN"),
        (tr(config, "external_check"), "OK" if detected.get("external_ok") else "WARN"),
    ])


def prompt_value(label, current):
    value = input(f"{label} [{current}]: ").strip()
    return value or current


def edit_detected_config(config):
    print(tr(config, "manual_prompt"))
    config.iface = prompt_value("IFACE", config.iface)
    config.gateway = prompt_value("GATEWAY", config.gateway)
    config.prefix = prompt_value("PREFIX", config.prefix)
    config.keep_addrs = prompt_value("KEEP_ADDRS", config.keep_addrs)
    config.healthcheck_mode = prompt_value("HEALTHCHECK_MODE", config.healthcheck_mode)


def timer_active():
    return command_exists("systemctl") and run(["systemctl", "is-active", "--quiet", "ipv6-rotate.timer"]).returncode == 0


def timer_enabled():
    if not command_exists("systemctl"):
        return "unknown"
    result = run(["systemctl", "is-enabled", "ipv6-rotate.timer"])
    return result.stdout.strip() or "unknown"


def timer_next():
    if not command_exists("systemctl"):
        return "unknown"
    result = run(["systemctl", "list-timers", "ipv6-rotate.timer", "--all", "--no-pager", "--no-legend"])
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("n/a"):
            continue
        parts = line.split()
        if len(parts) >= 4:
            return " ".join(parts[:4])
        return line
    return "unknown"


def normalize_interval(value, config=None):
    config = config or Config()
    value = (value or "").strip()
    if not value:
        usage_error(tr(config, "interval_empty"))
    if value.isdigit():
        return f"{value}s"
    allowed_suffixes = ("s", "sec", "min", "m", "h", "hour", "hours", "d", "day", "days")
    if any(value.endswith(suffix) for suffix in allowed_suffixes):
        return value
    usage_error(tr(config, "interval_invalid"))


def timer_interval():
    if not command_exists("systemctl"):
        return "unknown"

    result = run(["systemctl", "show", "ipv6-rotate.timer", "--property=TimersMonotonic", "--value"])
    for line in result.stdout.splitlines():
        if "OnUnitActiveUSec=" in line:
            value = line.split("OnUnitActiveUSec=", 1)[1].split(";", 1)[0].strip()
            return value or "unknown"

    result = run(["systemctl", "cat", "ipv6-rotate.timer"])
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("OnUnitActiveSec="):
            return line.split("=", 1)[1].strip() or "unknown"

    return "unknown"


def set_timer_interval(interval, config=None):
    config = config or Config()
    need_root(config)
    interval = normalize_interval(interval, config)
    TIMER_OVERRIDE_DIR.mkdir(parents=True, exist_ok=True)
    TIMER_OVERRIDE_FILE.write_text(f"[Timer]\nOnUnitActiveSec=\nOnUnitActiveSec={interval}\n", encoding="utf-8")
    run(["systemctl", "daemon-reload"], check=True)
    if timer_active():
        run(["systemctl", "restart", "ipv6-rotate.timer"], check=True)
    return interval


def systemctl_timer(action):
    config = Config()
    need_root(config)
    commands = {
        "enable": ["systemctl", "enable", "--now", "ipv6-rotate.timer"],
        "disable": ["systemctl", "disable", "--now", "ipv6-rotate.timer"],
        "restart": ["systemctl", "restart", "ipv6-rotate.timer"],
    }
    run(commands[action], check=True)


def timer_details():
    if not command_exists("systemctl"):
        return {"active": "unknown", "enabled": "unknown", "next": "unknown", "last": "unknown", "interval": "unknown"}
    active = "yes" if timer_active() else "no"
    enabled = timer_enabled()
    last_result = run(["systemctl", "show", "ipv6-rotate.timer", "--property=LastTriggerUSec", "--value"])
    last = last_result.stdout.strip() or "unknown"

    return {
        "active": active,
        "enabled": enabled,
        "next": timer_next(),
        "last": last,
        "interval": timer_interval(),
    }


def public_ipv6(config):
    if not command_exists("curl"):
        return "unavailable"
    for url in config.urls:
        result = run(["curl", "-6", "-fsS", "--max-time", "8", url])
        value = result.stdout.strip()
        if result.returncode == 0 and value:
            return value
    return "unavailable"


def ping_result(label, args):
    result = run(args)
    if result.returncode == 0:
        elapsed = "ok"
        for part in result.stdout.replace("\n", " ").split():
            if part.startswith("time="):
                elapsed = part.split("=", 1)[1] + " ms"
                break
        return [label, "OK", elapsed]
    return [label, "WARN", "failed"]


def gateway_ping_ok(config):
    return run(["ping", "-6", "-c", "1", "-W", "3", "-I", config.iface, config.gateway]).returncode == 0


def external_check_ok(config, source_ip):
    for host in config.ping_hosts:
        log(config, f"healthcheck: ping {host}")
        if run(["ping", "-6", "-c", "1", "-W", "3", "-I", source_ip, host]).returncode == 0:
            return True
    if command_exists("curl"):
        for url in config.urls:
            log(config, f"healthcheck: curl {url}")
            if run(["curl", "-6", "-fsS", "--max-time", "10", "--interface", source_ip, url]).returncode == 0:
                return True
    return False


def healthcheck(config, source_ip):
    source = source_ip or config.iface
    mode = normalize_healthcheck_mode(config.healthcheck_mode)

    def run_once():
        if mode == "basic":
            log(config, f"healthcheck: basic ping gateway {config.gateway}")
            return gateway_ping_ok(config)
        if mode == "normal":
            log(config, f"healthcheck: normal for {source}")
            return gateway_ping_ok(config) and external_check_ok(config, source)
        log(config, f"healthcheck: {mode} for {source}")
        public = public_ipv6(config)
        public_match = bool(source_ip and public == normalize_ip(source_ip))
        return gateway_ping_ok(config) and external_check_ok(config, source) and public_match

    ok = run_once()
    if ok and mode == "paranoid":
        time.sleep(3)
        ok = run_once()
    return ok


def notify_fail(config, message):
    if not config.webhook_url or not command_exists("curl"):
        return
    payload = json.dumps({"text": message})
    run(["curl", "-fsS", "--max-time", "10", "-H", "Content-Type: application/json", "-d", payload, config.webhook_url])


def add_new_ip(config, attempts=20):
    last_error = ""
    for _ in range(attempts):
        new_ip = generate_ip(config)
        if is_reserved_generated_ip(config, new_ip):
            last_error = "generated only reserved IPv6 addresses"
            log(config, f"reserved IPv6 generated, retrying: {new_ip}")
            continue
        log(config, f"target IPv6: {new_ip}")
        result = run(["ip", "-6", "addr", "add", f"{new_ip}/64", "dev", config.iface])
        if result.returncode == 0:
            return new_ip
        last_error = result.stderr.strip() or "failed to add IPv6 address"
        log(config, f"add failed, retrying: {last_error}")
    raise SystemExit(last_error)


def deprecate_old_addresses(config, current):
    deprecated = []
    for cidr in global_addresses(config):
        old_addr = normalize_ip(cidr)
        if not ip_in_prefix(old_addr, config.prefix) or old_addr == current:
            continue
        if is_keep_addr(config, old_addr):
            log(config, f"keep: {old_addr}/64")
            continue
        log(config, f"deprecating old IPv6: {old_addr}/64 preferred_lft 0 valid_lft {config.grace_seconds}")
        run(["ip", "-6", "addr", "change", f"{old_addr}/64", "dev", config.iface, "preferred_lft", "0", "valid_lft", str(config.grace_seconds)])
        deprecated.append(old_addr)
    return deprecated


def cleanup_old_addresses(config, max_old=None):
    now = int(time.time())
    removed = []
    for item in previous_items():
        ip = item.get("ip", "")
        if not ip or not ip_in_prefix(ip, config.prefix):
            continue
        deprecated_at = int(item.get("deprecated_at") or item.get("created_at") or now)
        if is_keep_addr(config, ip):
            log(config, f"keep: {ip}/64")
        elif now - deprecated_at >= config.grace_seconds:
            log(config, f"removing old IPv6: {ip}/64")
            run(["ip", "-6", "addr", "del", f"{ip}/64", "dev", config.iface])
            state_remove_previous(ip)
            removed.append(ip)
        else:
            log(config, f"grace: keeping {ip}/64")
    limit = config.max_old_addrs if max_old is None else max_old
    if limit is not None and limit >= 0:
        old = []
        for item in previous_items():
            ip = item.get("ip", "")
            if ip and ip_in_prefix(ip, config.prefix) and not is_keep_addr(config, ip):
                timestamp = int(item.get("deprecated_at") or item.get("created_at") or now)
                old.append((timestamp, ip))
        old.sort()
        overflow = max(0, len(old) - limit)
        for _, ip in old[:overflow]:
            log(config, f"removing old IPv6 over limit: {ip}/64")
            run(["ip", "-6", "addr", "del", f"{ip}/64", "dev", config.iface])
            state_remove_previous(ip)
            removed.append(ip)
    return removed


def rollback_route(config, old_route):
    if old_route:
        log(config, f"rollback: restoring old default route: {old_route}")
        result = run(["ip", "-6", "route", "replace", *old_route.split()])
        if result.returncode == 0:
            return True
        error = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        log(config, f"ERROR: rollback failed to restore old default route: {error}")
        return False
    log(config, "rollback: no old default route captured")
    return False


def remove_added_ip(config, new_ip):
    log(config, f"rollback: removing new IPv6 address {new_ip}/64")
    result = run(["ip", "-6", "addr", "del", f"{new_ip}/64", "dev", config.iface])
    if result.returncode == 0:
        return True
    error = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
    log(config, f"ERROR: rollback failed to remove new IPv6 address {new_ip}/64: {error}")
    return False


def fail_rotation_after_add(config, new_ip, old_route, old_src, reason):
    log(config, f"ERROR: {reason}")
    route_restored = rollback_route(config, old_route)
    ip_removed = remove_added_ip(config, new_ip)
    rollback_status = f"route_restored={route_restored}, new_ip_removed={ip_removed}"
    state_update(old_src, "fail", f"{reason}; rollback attempted ({rollback_status})")
    notify_fail(config, f"IPv6 rotation failed on {socket.gethostname()}: new_ip={new_ip}; reason={reason}; {rollback_status}")
    raise SystemExit(1)


def acquire_lock(config=None):
    config = config or Config()
    try:
        import fcntl
    except ImportError:
        return None
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    fh = LOCK_FILE.open("w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(tr(config, "already_running"))
    return fh


def cmd_rotate(args):
    config = Config()
    need_root(config)
    require_config(config)
    detect_network(config)
    lock = acquire_lock(config)
    old_route = default_route()
    old_src = default_src()
    now = int(time.time())
    log(config, f"old default route: {old_route or 'none'}")
    log(config, f"old default src: {old_src or 'none'}")

    new_ip = add_new_ip(config)

    log(config, f"waiting for IPv6 address to become ready: {new_ip}/64")
    ready_error = wait_for_address_ready(config, new_ip)
    if ready_error:
        fail_rotation_after_add(config, new_ip, old_route, old_src, ready_error)

    log(config, f"setting default route src {new_ip}")
    route_result = run(["ip", "-6", "route", "replace", "default", "via", config.gateway, "dev", config.iface, "src", new_ip])
    if route_result.returncode != 0:
        error = route_result.stderr.strip() or route_result.stdout.strip() or f"exit code {route_result.returncode}"
        fail_rotation_after_add(config, new_ip, old_route, old_src, f"failed to set default route src {new_ip}: {error}")

    time.sleep(2)
    if healthcheck(config, new_ip):
        log(config, f"healthcheck passed for {new_ip}")
        deprecated = deprecate_old_addresses(config, new_ip)
        state_update(new_ip, "success", "rotation complete", old_src, now, deprecated)
        removed = cleanup_old_addresses(config)
        if removed:
            log(config, f"cleanup removed {len(removed)} old IPv6 address(es)")
        log(config, f"IPv6 rotation complete: {new_ip}")
    else:
        reason = f"healthcheck failed for {new_ip}"
        fail_rotation_after_add(config, new_ip, old_route, old_src, reason)
    return 0


def cmd_dry_run(args):
    config = Config()
    require_config(config)
    detect_network(config)
    route_src = default_src()
    new_ip = ""
    for _ in range(20):
        candidate = generate_ip(config)
        if not is_reserved_generated_ip(config, candidate):
            new_ip = candidate
            break
    if not new_ip:
        raise SystemExit(tr(config, "could_not_generate_ip"))
    now = int(time.time())

    print(f"{tr(config, 'dry_run_title')}\n")
    print(f"{tr(config, 'would_add')}:")
    print(f"  {new_ip}/64\n")
    print(f"{tr(config, 'would_set_default_route')}:")
    print(f"  default via {config.gateway} dev {config.iface} src {new_ip}\n")
    print(f"{tr(config, 'would_keep')}:")
    for keep in config.keep_list:
        print(f"  {keep}/64")
    if route_src:
        print(f"  {route_src}/64")

    print(f"\n{tr(config, 'would_deprecate')}:")
    deprecated = []
    for cidr in global_addresses(config):
        addr = normalize_ip(cidr)
        if ip_in_prefix(addr, config.prefix) and addr != route_src and not is_keep_addr(config, addr):
            deprecated.append(f"{addr}/64")
    print("\n".join(f"  {item}" for item in deprecated) if deprecated else f"  {tr(config, 'none')}")

    print(f"\n{tr(config, 'would_remove_after_grace')}:")
    removable = []
    for item in previous_items():
        ip = item.get("ip", "")
        deprecated_at = int(item.get("deprecated_at") or item.get("created_at") or now)
        if ip and now - deprecated_at >= config.grace_seconds:
            removable.append(f"{ip}/64")
    print("\n".join(f"  {item}" for item in removable) if removable else f"  {tr(config, 'none')}")


def cmd_cleanup(args):
    config = Config()
    need_root(config)
    require_config(config)
    detect_network(config)
    lock = acquire_lock(config)
    removed = cleanup_old_addresses(config, getattr(args, "max_old", None))
    if wants_json(args):
        print_records_json({"removed": removed, "removed_count": len(removed)})
    else:
        print_plain_kv([kv(config, "removed", len(removed)), kv(config, "max_old_addresses", getattr(args, "max_old", None) if getattr(args, "max_old", None) is not None else config.max_old_addrs)])
    return 0


def cmd_test(args):
    config = Config()
    require_config(config)
    detect_network(config)
    if not healthcheck(config, default_src()):
        raise SystemExit(1)
    log(config, "healthcheck passed")


def cmd_healthcheck(args):
    config = Config()
    require_config(config)
    detect_network(config)
    mode = normalize_healthcheck_mode(getattr(args, "mode", "") or config.healthcheck_mode)
    if mode not in HEALTHCHECK_MODES:
        usage_error(tr(config, "healthcheck_mode_invalid"))
    config.healthcheck_mode = mode
    source = default_src()
    ok = healthcheck(config, source)
    payload = {"mode": mode, "route_src": source or "unknown", "ok": ok}
    if wants_json(args):
        print_records_json(payload)
    else:
        print_plain_kv([kv(config, "healthcheck_mode", mode), kv(config, "route_src", source or "unknown"), kv(config, "result", "OK" if ok else "FAIL")])
    raise SystemExit(0 if ok else 1)


def cmd_detect(args):
    config = Config()
    detected = detect_config(config)
    if getattr(args, "json", False):
        print(json.dumps({
            "interface": config.iface,
            "prefix": config.prefix,
            "gateway": config.gateway,
            "keep_addrs": config.keep_addrs.split(),
            "route_src": detected.get("route_src") or "unknown",
            "public_ipv6": detected.get("public_ipv6") or "unknown",
            "gateway_ping": bool(detected.get("gateway_ok")),
            "external_check": bool(detected.get("external_ok")),
            "addresses": detected.get("addresses", []),
        }, indent=2))
        return
    render_detected_config(config, detected)


def cmd_setup(args):
    config = Config()
    need_root()
    while True:
        detected = detect_config(config)
        render_detected_config(config, detected)
        print()
        print(tr(config, "use_config"))
        print(f"  1) {tr(config, 'save_config')}")
        print(f"  2) {tr(config, 'change_values')}")
        print(f"  3) {tr(config, 'show_addresses')}")
        print(f"  4) {tr(config, 'cancel')}")
        choice = input("> ").strip()
        if choice == "1":
            write_config_file(config)
            print(tr(config, "setup_saved", path=CONFIG_FILE))
            print()
            if input(tr(config, "run_validation")).strip().lower() not in {"n", "no"}:
                try:
                    cmd_validate(argparse.Namespace())
                except SystemExit as exc:
                    if exc.code not in (None, 0):
                        print(tr(config, "setup_validation_failed", code=exc.code))
            print()
            print(f"{tr(config, 'next_commands')}:")
            print("  ipv6-rotate validate")
            print("  ipv6-rotate dry-run")
            return
        if choice == "2":
            edit_detected_config(config)
            continue
        if choice == "3":
            rows = []
            for item in detected.get("addresses", []):
                flags = []
                if item.get("deprecated"):
                    flags.append("deprecated")
                if item.get("dynamic"):
                    flags.append("dynamic")
                if item.get("temporary"):
                    flags.append("temporary")
                if detected.get("route_src") and normalize_ip(item["ip"]) == normalize_ip(detected["route_src"]):
                    flags.append("route-src")
                rows.append([item["ip"], ", ".join(flags) or "static", item.get("preferred_lft", "unknown")])
            table_rows(tr(config, "addresses_title"), ["IPv6", tr(config, "status"), "preferred_lft"], rows or [["-", "WARN", tr(config, "missing")]])
            continue
        if choice == "4":
            print(tr(config, "cancelled"))
            return
        print(tr(config, "unknown_option", choice=choice))


def cmd_language(args):
    config = Config()
    if getattr(args, "interactive", False):
        while True:
            table_kv(tr(config, "language_menu_title"), [
                ("LANGUAGE", config.language),
                (tr(config, "resolved"), resolve_language(config.language)),
            ])
            print("  1) auto")
            print("  2) en")
            print("  3) ru")
            print("  0) " + tr(config, "cancel"))
            choice = input(tr(config, "choose_option")).strip()
            if choice == "0":
                return
            selected = {"1": "auto", "2": "en", "3": "ru"}.get(choice)
            if selected:
                config.language = selected
                write_config_file(config)
                print(tr(config, "language_saved", language=selected))
                return
            print(tr(config, "unknown_option", choice=choice))
    if not getattr(args, "language", None):
        table_kv(tr(config, "language"), [
            ("LANGUAGE", config.language),
            (tr(config, "resolved"), resolve_language(config.language)),
            (tr(config, "config_file"), str(CONFIG_FILE)),
        ])
        return
    language = normalize_language(args.language)
    if language != args.language:
        raise SystemExit(tr(config, "language_invalid"))
    config.language = language
    write_config_file(config)
    print(f"LANGUAGE={language}")


def last_rotation_summary(state):
    last = state.get("last_rotation", {})
    status = last.get("status", "unknown")
    created_at = last.get("created_at")
    if created_at:
        when = dt.datetime.fromtimestamp(int(created_at)).strftime("%F %T")
        return f"{status}, {when}"
    return status


def cmd_status(args):
    config = Config()
    require_config(config)
    detect_network(config)
    state = load_state()
    route_src = default_src()
    public_ip = public_ipv6(config)
    timer = timer_active()
    details = timer_details()
    health = "ok" if route_src and public_ip == route_src else "warn"

    payload = {
        "interface": config.iface,
        "prefix": config.prefix,
        "gateway": config.gateway,
        "route_src": route_src or "unknown",
        "public_ipv6": public_ip,
        "timer_active": timer,
        "timer_enabled": details.get("enabled", "unknown"),
        "rotation_interval": details.get("interval", "unknown"),
        "grace_seconds": config.grace_seconds,
        "next_rotation": details.get("next", "unknown"),
        "old_addresses": len(state.get("previous", [])),
        "max_old_addresses": config.max_old_addrs,
        "last_rotation_status": state.get("last_rotation", {}).get("status", "unknown"),
        "health": health,
    }

    if wants_json(args):
        print_records_json(payload)
        return

    pairs = [
        kv(config, "interface", config.iface),
        kv(config, "prefix", str(prefix_network(config.prefix))),
        kv(config, "gateway", config.gateway),
        kv(config, "healthcheck_mode", config.healthcheck_mode),
        kv(config, "current_route_src", route_src or "unknown"),
        kv(config, "public_ipv6", public_ip),
        kv(config, "keep_addresses", len(config.keep_list)),
        kv(config, "old_addresses", f"{len(state.get('previous', []))}/{config.max_old_addrs}"),
        kv(config, "rotation_interval", details.get("interval", "unknown")),
        kv(config, "grace_period", f"{config.grace_seconds}s"),
        kv(config, "timer", "active" if timer else "inactive"),
        kv(config, "timer_enabled", details.get("enabled", "unknown")),
        kv(config, "next_rotation", details.get("next", "unknown")),
        kv(config, "last_rotation", last_rotation_summary(state)),
        kv(config, "health", health.upper()),
    ]

    if not wants_table(args):
        print_plain_kv(pairs)
        return

    table_kv(tr(config, "status_title"), [
        (label, value) for label, value in pairs
    ])

    first_host = config.ping_hosts[0] if config.ping_hosts else ""
    rows = []
    if config.healthcheck_mode in {"basic", "normal", "strict", "paranoid"}:
        rows.append(ping_result(tr(config, "gateway_ping"), ["ping", "-6", "-c", "1", "-W", "3", "-I", config.iface, config.gateway]))
    else:
        rows.append([tr(config, "gateway_ping"), "SKIP", config.healthcheck_mode])
    if first_host and route_src:
        rows.append(ping_result("Cloudflare IPv6 ping", ["ping", "-6", "-c", "1", "-W", "3", "-I", route_src, first_host]))
    else:
        rows.append(["Cloudflare IPv6 ping", "WARN", tr(config, "no_route_source")])
    if public_ip == "unavailable":
        rows.append([tr(config, "public_ipv6"), "WARN", tr(config, "unavailable")])
    elif route_src and public_ip == route_src:
        rows.append([tr(config, "public_ipv6"), "OK", tr(config, "matched")])
    else:
        rows.append([tr(config, "public_ipv6"), "OK", public_ip])
    if route_src and public_ip == route_src:
        rows.append([tr(config, "route_src_match"), "OK", tr(config, "matched")])
    elif public_ip == "unavailable":
        rows.append([tr(config, "route_src_match"), "WARN", tr(config, "public_ipv6_unavailable")])
    else:
        rows.append([tr(config, "route_src_match"), "WARN", f"route={route_src or tr(config, 'unknown')} public={public_ip}"])
    print()
    table_rows(tr(config, "healthcheck"), [tr(config, "check"), tr(config, "status"), tr(config, "result")], rows)


def cmd_validate(args):
    config = Config()
    require_config(config)
    rows = []
    failed = False
    rows.append(check_row(config, "root_check", "OK" if hasattr(os, "geteuid") and os.geteuid() == 0 else "FAIL", "root" if hasattr(os, "geteuid") and os.geteuid() == 0 else "not root"))
    failed = failed or rows[-1][1] == "FAIL"

    for dep in ["python3", "ip", "ping"]:
        path = shutil.which(dep)
        rows.append([tr(config, "validate_installed", dep=dep), "OK" if path else "FAIL", path or tr(config, "missing")])
        failed = failed or not path
    for dep in ["curl", "systemctl", "journalctl"]:
        path = shutil.which(dep)
        rows.append([tr(config, "validate_recommended", dep=dep), "OK" if path else "WARN", path or tr(config, "missing")])
    for dep in ["bash", "awk", "sed"]:
        path = shutil.which(dep)
        rows.append([tr(config, "validate_installer_only", dep=dep), "OK" if path else "WARN", path or tr(config, "missing")])

    try:
        network = prefix_network(config.prefix)
        rows.append(check_row(config, "prefix_format", "OK", str(network)))
    except Exception:
        rows.append(check_row(config, "prefix_format", "FAIL", "invalid PREFIX"))
        failed = True

    mode_ok = config.healthcheck_mode in HEALTHCHECK_MODES
    rows.append(check_row(config, "healthcheck_mode", "OK" if mode_ok else "FAIL", config.healthcheck_mode))
    failed = failed or not mode_ok

    try:
        detect_network(config)
        rows.append(check_row(config, "network_detected", "OK", f"{config.iface} via {config.gateway}"))
    except SystemExit as exc:
        rows.append(check_row(config, "network_detected", "FAIL", str(exc)))
        failed = True

    iface_ok = bool(config.iface) and run(["ip", "link", "show", "dev", config.iface]).returncode == 0
    rows.append(check_row(config, "interface_exists", "OK" if iface_ok else "FAIL", config.iface or "missing"))
    failed = failed or not iface_ok

    keep_ok = True
    for keep in config.keep_list:
        keep_ok = keep_ok and ip_in_prefix(keep, config.prefix)
    rows.append(check_row(config, "keep_in_prefix", "OK" if keep_ok else "FAIL", f"{len(config.keep_list)} address(es)"))
    failed = failed or not keep_ok

    if iface_ok:
        present = {normalize_ip(cidr) for cidr in global_addresses(config)}
        missing_keep = [keep for keep in config.keep_list if keep not in present]
        rows.append([
            tr(config, "keep_assigned"),
            "OK" if not missing_keep else "FAIL",
            tr(config, "all_present") if not missing_keep else ", ".join(missing_keep),
        ])
        failed = failed or bool(missing_keep)

    if config.iface and config.gateway and config.healthcheck_mode in {"basic", "normal", "strict", "paranoid"}:
        rows.append(check_row(config, "gateway_reachable", "OK" if gateway_ping_ok(config) else "WARN", config.gateway))
    else:
        rows.append(check_row(config, "gateway_reachable", "SKIP", config.healthcheck_mode if config.healthcheck_mode not in {"basic", "normal", "strict", "paranoid"} else "IFACE/GATEWAY missing"))

    timer_found = command_exists("systemctl") and run(["systemctl", "list-unit-files", "ipv6-rotate.timer"]).returncode == 0
    rows.append(check_row(config, "systemd_timer_installed", "OK" if timer_found else "WARN", "ipv6-rotate.timer" if timer_found else "not found"))
    table_rows(tr(config, "validation_title"), [tr(config, "check"), tr(config, "status"), tr(config, "details")], rows)
    raise SystemExit(1 if failed else 0)


def cmd_doctor(args):
    config = Config()
    require_config(config)
    rows = []
    failed = False

    try:
        detect_network(config)
        rows.append(check_row(config, "config", "OK", f"{config.iface} via {config.gateway}"))
    except SystemExit as exc:
        rows.append(check_row(config, "config", "FAIL", str(exc)))
        failed = True

    rows.append(check_row(config, "healthcheck_mode", "OK" if config.healthcheck_mode in HEALTHCHECK_MODES else "FAIL", config.healthcheck_mode))
    failed = failed or config.healthcheck_mode not in HEALTHCHECK_MODES

    for dep in ["ip", "ping", "curl", "systemctl"]:
        path = shutil.which(dep)
        status = "OK" if path else ("WARN" if dep in {"curl", "systemctl"} else "FAIL")
        rows.append([f"{tr(config, 'command')} {dep}", status, path or tr(config, "missing")])
        failed = failed or status == "FAIL"

    route = default_route() if command_exists("ip") else ""
    route_src = default_src() if command_exists("ip") else ""
    rows.append(check_row(config, "default_route", "OK" if route else "FAIL", route or "missing"))
    rows.append(check_row(config, "route_src", "OK" if route_src else "WARN", route_src or "unknown"))
    failed = failed or not route

    if config.iface and command_exists("ip"):
        addrs = [normalize_ip(cidr) for cidr in global_addresses(config) if ip_in_prefix(normalize_ip(cidr), config.prefix)]
        rows.append(check_row(config, "rotated_prefix_addrs", "OK" if addrs else "WARN", str(len(addrs))))

    if config.iface and config.gateway and config.healthcheck_mode in {"basic", "normal", "strict", "paranoid"}:
        rows.append(check_row(config, "gateway_ping", "OK" if gateway_ping_ok(config) else "WARN", config.gateway))
    elif config.healthcheck_mode not in {"basic", "normal", "strict", "paranoid"}:
        rows.append(check_row(config, "gateway_ping", "SKIP", config.healthcheck_mode))

    if route_src:
        external = external_check_ok(config, route_src)
        rows.append(check_row(config, "external_ipv6", "OK" if external else "WARN", "ping/curl via route src"))

    state = load_state()
    last_error = state.get("last_error")
    rows.append(check_row(config, "timer_active", "OK" if timer_active() else "WARN", "active" if timer_active() else "inactive"))
    rows.append(check_row(config, "next_rotation", "INFO", timer_next()))
    rows.append(check_row(config, "last_rotation", "INFO", last_rotation_summary(state)))
    rows.append(check_row(config, "last_error", "WARN" if last_error else "OK", json.dumps(last_error) if last_error else "none"))
    if wants_json(args):
        print_records_json({"failed": failed, "checks": [{"check": r[0], "status": r[1], "details": r[2]} for r in rows]})
    elif wants_table(args):
        table_rows(tr(config, "doctor_title"), [tr(config, "check"), tr(config, "status"), tr(config, "details")], rows)
    else:
        for check, status, details in rows:
            print(f"{status:<5} {check}: {details}")
    raise SystemExit(1 if failed else 0)


def cmd_timer(args):
    details = timer_details()
    config = Config()
    action = getattr(args, "timer_action", "show") or "show"
    if action == "set":
        if not getattr(args, "interval", ""):
            usage_error(tr(config, "usage_timer_set"))
        interval = set_timer_interval(args.interval, config)
        print_plain_kv([kv(config, "rotation_interval", interval), ("Override", str(TIMER_OVERRIDE_FILE))])
        return
    if action in {"enable", "disable", "restart"}:
        systemctl_timer(action)
        print_plain_kv([kv(config, "timer_action_done", action), kv(config, "result", "OK")])
        return
    pairs = [
        kv(config, "timer_active", details.get("active", "unknown")),
        kv(config, "timer_enabled", details.get("enabled", "unknown")),
        kv(config, "next_rotation", details.get("next", "unknown")),
        kv(config, "last_trigger", details.get("last", "unknown")),
        kv(config, "interval", details.get("interval", "unknown")),
    ]
    if wants_json(args):
        print_records_json(details)
    elif wants_table(args):
        table_kv(tr(config, "timer_title"), pairs)
    else:
        print_plain_kv(pairs)


def cmd_config(args):
    config = Config()
    action = getattr(args, "config_action", "show") or "show"
    if action == "set":
        if not getattr(args, "key", None) or getattr(args, "value", None) is None:
            usage_error(tr(config, "usage_config_set"))
        config_set(args.key, args.value)
        return
    pairs = [
        kv(config, "config_file", str(CONFIG_FILE)),
        kv(config, "interface", config.iface or tr(config, "auto")),
        kv(config, "prefix", config.prefix or tr(config, "missing")),
        kv(config, "gateway", config.gateway or tr(config, "auto")),
        kv(config, "keep_addresses", config.keep_addrs or tr(config, "auto")),
        kv(config, "language", config.language),
        kv(config, "grace_seconds", str(config.grace_seconds)),
        kv(config, "max_old_addresses", str(config.max_old_addrs)),
        kv(config, "healthcheck_mode", config.healthcheck_mode),
        kv(config, "ping_checks", config.healthcheck_ping6),
        kv(config, "url_checks", config.healthcheck_urls),
        kv(config, "webhook", "set" if config.webhook_url else tr(config, "not_set")),
        kv(config, "log_file", str(config.log_file)),
        kv(config, "state_file", str(STATE_FILE)),
    ]
    if wants_json(args):
        print_records_json(config_values(config))
    elif wants_table(args):
        table_kv(tr(config, "config_title"), pairs)
    else:
        print_plain_kv(pairs)


def cmd_edit_config(args):
    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, str(CONFIG_FILE)], check=False)


def cmd_enable(args):
    systemctl_timer("enable")


def cmd_disable(args):
    systemctl_timer("disable")


def cmd_restart_timer(args):
    systemctl_timer("restart")


def rollback_target(args, state):
    explicit = getattr(args, "ip", "")
    if explicit:
        return normalize_ip(explicit)
    previous = state.get("previous", [])
    for item in previous:
        if item.get("ip"):
            return normalize_ip(item["ip"])
    return normalize_ip(state.get("current", "")) if state.get("current") else ""


def cmd_rollback(args):
    config = Config()
    need_root(config)
    require_config(config)
    detect_network(config)
    state = load_state()
    target = rollback_target(args, state)
    if not target:
        raise SystemExit(tr(config, "rollback_no_previous", path=STATE_FILE))
    if not ip_in_prefix(target, config.prefix):
        raise SystemExit(tr(config, "rollback_outside_prefix", target=target))
    if not address_exists(config, target):
        if not getattr(args, "restore_address", False):
            raise SystemExit(tr(config, "rollback_not_assigned", iface=config.iface, target=target))
        log(config, f"rollback: restoring missing IPv6 address {target}/64 on {config.iface}")
        result = run(["ip", "-6", "addr", "add", f"{target}/64", "dev", config.iface])
        if result.returncode != 0:
            raise SystemExit(result.stderr.strip() or tr(config, "restore_address_failed", target=target))
    old_src = default_src()
    log(config, f"rollback: setting default route src {target}")
    run(["ip", "-6", "route", "replace", "default", "via", config.gateway, "dev", config.iface, "src", target], check=True)
    state_update(target, "success", "rollback complete", old_src)


def rescue_target(config):
    state = load_state()
    target = rollback_target(argparse.Namespace(ip="", restore_address=False), state)
    if not target:
        target = default_src() or (config.keep_list[0] if config.keep_list else "")
    return target


def print_rescue_commands(config, target):
    if target:
        print(f"ip -6 addr add {target}/64 dev {config.iface}")
        print(f"ip -6 route replace default via {config.gateway} dev {config.iface} src {target}")
    else:
        print(f"# {tr(config, 'no_rescue_ipv6')}")
        print(f"# ip -6 route replace default via {config.gateway} dev {config.iface} src <IPv6>")


def cmd_print_rescue(args):
    config = Config()
    require_config(config)
    detect_network(config)
    print_rescue_commands(config, rescue_target(config))


def cmd_restore_route(args):
    config = Config()
    need_root(config)
    require_config(config)
    detect_network(config)
    target = getattr(args, "ip", "") or rescue_target(config)
    if not target:
        raise SystemExit(tr(config, "no_route_source"))
    target = normalize_ip(getattr(args, "ip", "") or rescue_target(config))
    run(["ip", "-6", "route", "replace", "default", "via", config.gateway, "dev", config.iface, "src", target], check=True)
    print_plain_kv([kv(config, "route_src", target), kv(config, "result", "OK")])


def cmd_emergency(args):
    config = Config()
    print(f"{tr(config, 'emergency_title')}:")
    try:
        require_config(config)
        detect_network(config)
        print_rescue_commands(config, rescue_target(config))
    except SystemExit as exc:
        print(f"# {tr(config, 'config_incomplete', error=exc)}")
        print(f"# {tr(config, 'run')}: ip -6 route show default")
        print(f"# {tr(config, 'run')}: ip -o -6 addr show scope global")


def safe_checks(config):
    state = load_state()
    route_src = default_src()
    public_ip = public_ipv6(config)
    keep_present = all(address_exists(config, keep) for keep in config.keep_list)
    last = state.get("last_rotation", {})
    old_count = len(state.get("previous", []))
    checks = [
        ("timer_active", timer_active(), "active" if timer_active() else "inactive"),
        ("timer_enabled", timer_enabled() in {"enabled", "static"}, timer_enabled()),
        ("route_src_matches_public", bool(route_src and public_ip == route_src), f"route={route_src or 'unknown'} public={public_ip}"),
        ("gateway_reachable", gateway_ping_ok(config), config.gateway),
        ("external_ipv6_reachable", external_check_ok(config, route_src) if route_src else False, route_src or "no route src"),
        ("keep_assigned", keep_present, "all present" if keep_present else "missing"),
        ("old_addresses_count_ok", old_count <= config.max_old_addrs, f"{old_count}/{config.max_old_addrs}"),
        ("last_rotation_success", last.get("status", "unknown") in {"success", "unknown"}, last_rotation_summary(state)),
        ("next_rotation_scheduled", timer_next() != "unknown", timer_next()),
    ]
    return checks


def cmd_safe_check(args):
    config = Config()
    require_config(config)
    detect_network(config)
    checks = safe_checks(config)
    failed = [item for item in checks if not item[1]]
    if wants_json(args):
        print_records_json({"safe": not failed, "checks": [{"check": name, "ok": ok, "details": details} for name, ok, details in checks]})
    elif wants_table(args):
        table_rows(tr(config, "safe_check_title"), [tr(config, "check"), tr(config, "status"), tr(config, "details")], [[tr(config, name), "OK" if ok else "FAIL", tv(config, details)] for name, ok, details in checks])
        print()
        print(f"{tr(config, 'result')}: {tr(config, 'safe_result') if not failed else tr(config, 'unsafe_result')}")
    else:
        for name, ok, details in checks:
            print(f"{'OK' if ok else 'FAIL':<5} {tr(config, name)}: {tv(config, details)}")
        print(f"{tr(config, 'result')}: {tr(config, 'safe_result') if not failed else tr(config, 'unsafe_result')}")
    raise SystemExit(0 if not failed else 1)


def cmd_purge(args):
    config = Config()
    need_root(config)
    if not getattr(args, "yes", False) and not confirm(tr(config, "cleanup_confirm"), config):
        print(tr(config, "cancelled"))
        return
    for path in [CONFIG_FILE, config.log_file]:
        try:
            path.unlink()
            print(tr(config, "purge_removed", path=path))
        except FileNotFoundError:
            pass
    shutil.rmtree(STATE_DIR, ignore_errors=True)
    print(tr(config, "purge_removed", path=STATE_DIR))


def cmd_version(args):
    config = Config()
    table_kv(tr(config, "version_title"), [
        kv(config, "version", VERSION),
        kv(config, "cli_path", str(Path(__file__).resolve())),
        kv(config, "config_file", str(CONFIG_FILE)),
        kv(config, "state_file", str(STATE_FILE)),
    ])


def cmd_notify_test(args):
    config = Config()
    if not config.webhook_url:
        raise SystemExit(tr(config, "webhook_not_set"))
    if not command_exists("curl"):
        raise SystemExit(tr(config, "curl_not_installed"))
    payload = json.dumps({"text": tr(config, "test_notification", host=socket.gethostname())})
    result = run(["curl", "-fsS", "--max-time", "10", "-H", "Content-Type: application/json", "-d", payload, config.webhook_url])
    if result.returncode == 0:
        print(tr(config, "notify_sent"))
        return
    raise SystemExit(result.stderr.strip() or tr(config, "failed_notification"))


def cmd_watch(args):
    interval = max(1, int(args.interval))
    try:
        while True:
            os.system("clear" if os.name != "nt" else "cls")
            try:
                cmd_status(argparse.Namespace(json=args.json))
            except SystemExit as exc:
                print(exc)
            time.sleep(interval)
    except KeyboardInterrupt:
        return


def address_role(config, addr, route_src):
    if is_keep_addr(config, addr):
        return "keep"
    if route_src and normalize_ip(addr) == normalize_ip(route_src):
        return "current"
    return "rotated"


def address_lifetime(item):
    if item["deprecated"]:
        return item["valid_lft"]
    preferred = item.get("preferred_lft", "unknown")
    if preferred == "forever":
        return "forever"
    return "preferred"


def cmd_addresses(args):
    config = Config()
    require_config(config)
    detect_network(config)
    route_src = default_src()
    rows = []
    for item in global_address_details(config):
        addr = item["ip"]
        if not ip_in_prefix(addr, config.prefix):
            continue
        role = "deprecated" if item["deprecated"] else address_role(config, addr, route_src)
        rows.append([addr, role, address_lifetime(item)])
    if not rows:
        print(tr(config, "no_addresses", network=prefix_network(config.prefix), iface=config.iface))
        return
    table_rows(tr(config, "addresses_title"), ["IPv6", tr(config, "address_role"), tr(config, "address_lifetime")], rows)


def cmd_self_test(args):
    rows = []
    failed = False

    def check(name, ok, details):
        nonlocal failed
        rows.append([name, "OK" if ok else "FAIL", details])
        failed = failed or not ok

    sample = "2001:0db8:abcd:1234:0000:0000:0000:0002"
    check("normalize_ip", normalize_ip(sample) == "2001:db8:abcd:1234::2", normalize_ip(sample))
    check("prefix matching", ip_in_prefix("2001:db8:abcd:1234::2", "2001:db8:abcd:1234"), "inside /64")

    cfg = Config()
    cfg.prefix = "2001:db8:abcd:1234"
    cfg.gateway = "2001:db8:abcd:1234::1"
    cfg.keep_addrs = "2001:db8:abcd:1234::2"
    generated = generate_ip(cfg)
    check("generate_ip prefix", ip_in_prefix(generated, cfg.prefix), generated)
    check("reserved gateway", is_reserved_generated_ip(cfg, cfg.gateway), cfg.gateway)
    check("reserved keep", is_reserved_generated_ip(cfg, cfg.keep_addrs), cfg.keep_addrs)
    check("reserved network", is_reserved_generated_ip(cfg, "2001:db8:abcd:1234::"), "prefix::")
    wrapped_cell = wrap_cell("https://example.invalid/very/long/path", 12)
    check("table cell wrapping", len(wrapped_cell) > 1 and all(len(line) <= 12 for line in wrapped_cell), f"{len(wrapped_cell)} lines")

    original_global_address_details = globals()["global_address_details"]
    ready_checks = [
        [{"ip": "2001:db8:abcd:1234::3", "tentative": True, "dadfailed": False, "deprecated": False}],
        [{"ip": "2001:db8:abcd:1234::3", "tentative": False, "dadfailed": False, "deprecated": False}],
    ]
    try:
        globals()["global_address_details"] = lambda _config: ready_checks.pop(0) if ready_checks else []
        ready_error = wait_for_address_ready(cfg, "2001:db8:abcd:1234::3", timeout=1, interval=0)
    finally:
        globals()["global_address_details"] = original_global_address_details
    check("address readiness wait", ready_error == "", "tentative -> ready")

    parsed = parse_env_file(CONFIG_FILE)
    check("config parse", isinstance(parsed, dict), f"{len(parsed)} value(s)")

    state = load_state()
    check("state read", isinstance(state, dict), f"{len(state)} key(s)")

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            table_kv("Table self-test", [("left", "right")])
            table_rows("Rows self-test", ["A", "B"], [["1", "2"]])
        table_ok = True
    except Exception as exc:
        table_ok = False
        table_error = str(exc)
    else:
        table_error = "rendered"
    check("table rendering", table_ok, table_error)

    help_stdout = io.StringIO()
    with contextlib.redirect_stdout(help_stdout):
        help_code = main(["help", "doctor"])
    help_text = help_stdout.getvalue()
    check("command help", help_code == 0 and "ipv6-rotate doctor" in help_text, "help doctor")

    error_stderr = io.StringIO()
    with contextlib.redirect_stderr(error_stderr):
        error_code = main(["not-a-command"])
    error_text = error_stderr.getvalue()
    check("invalid command help", error_code == 2 and "ipv6-rotate --help" in error_text, "clean error")

    table_rows("Self Test", ["Check", "Status", "Details"], rows)
    raise SystemExit(1 if failed else 0)


def cmd_history(args):
    config = Config()
    state = load_state()
    rows = []
    records = []
    last = state.get("last_rotation", {})
    if state.get("current"):
        created_at = last.get("created_at")
        when = dt.datetime.fromtimestamp(int(created_at)).strftime("%F %T") if created_at else tr(config, "unknown")
        rows.append([when, state["current"], last.get("status", "current")])
        records.append({"time": when, "ipv6": state["current"], "status": last.get("status", "current")})
    for item in state.get("previous", []):
        timestamp = item.get("deprecated_at") or item.get("created_at")
        when = dt.datetime.fromtimestamp(int(timestamp)).strftime("%F %T") if timestamp else tr(config, "unknown")
        rows.append([when, item.get("ip", ""), "deprecated"])
        records.append({"time": when, "ipv6": item.get("ip", ""), "status": "deprecated"})
    if wants_json(args):
        print_records_json(records)
        return
    if not rows:
        print(tr(config, "no_history", path=STATE_FILE))
        return
    if wants_table(args):
        table_rows(tr(config, "rotation_history_title"), [tr(config, "time"), "IPv6", tr(config, "status")], rows)
    else:
        for when, ip, status in rows:
            print(f"{when} {status:<10} {ip}")


def cmd_logs(args, replace_process=False):
    config = Config()
    if command_exists("journalctl"):
        if args.follow:
            cmd = ["journalctl", "-u", "ipv6-rotate.service", "-f"]
        else:
            cmd = ["journalctl", "-u", "ipv6-rotate.service", "-n", str(args.lines), "--no-pager"]
        if replace_process:
            os.execvp(cmd[0], cmd)
        subprocess.run(cmd, check=False)
        return
    if config.log_file.exists():
        if args.follow:
            cmd = ["tail", "-f", str(config.log_file)]
        else:
            cmd = ["tail", "-n", str(args.lines), str(config.log_file)]
        if replace_process:
            os.execvp(cmd[0], cmd)
        subprocess.run(cmd, check=False)
        return
    raise SystemExit(tr(config, "log_source_missing", path=config.log_file))


def confirm(message, config=None):
    config = config or Config()
    answer = input(f"{message}\n{tr(config, 'continue')}").strip().lower()
    return answer in {"y", "yes"}


def menu_call(func, *args):
    try:
        return func(*args)
    except SystemExit as exc:
        if exc.code not in (None, 0):
            print(exc)
        return None


def cmd_menu(args):
    config = Config()
    menu_text = {
        "en": """IPv6 Rotate Manager

  1) Show status
  2) Rotate now
  3) Dry-run rotation
  4) Validate config
  5) Run doctor
  6) Cleanup old IPv6 addresses
  7) Show history
  8) Show logs
  9) Show timer
 10) Edit config
 11) Restart timer
 12) Disable timer
 13) Enable timer
 14) Rollback to previous IPv6
 15) Watch status
 16) Send test notification
 17) Show IPv6 addresses
 18) Run self-test
 19) Detect IPv6 config
 20) Setup config
 21) Language
  0) Exit
""",
        "ru": """IPv6 Rotate Manager

  1) Показать статус
  2) Выполнить ротацию сейчас
  3) Пробный запуск ротации
  4) Проверить конфиг
  5) Запустить диагностику
  6) Очистить старые IPv6-адреса
  7) Показать историю
  8) Показать логи
  9) Показать таймер
 10) Редактировать конфиг
 11) Перезапустить таймер
 12) Отключить таймер
 13) Включить таймер
 14) Rollback на предыдущий IPv6
 15) Наблюдать статус
 16) Отправить тестовое уведомление
 17) Показать IPv6-адреса
 18) Запустить self-test
 19) Найти IPv6-конфигурацию
 20) Настроить конфиг
 21) Язык
  0) Выход
""",
    }
    while True:
        print(menu_text[resolve_language(config.language)])
        choice = input(tr(config, "choose_option")).strip()
        if choice == "1":
            menu_call(cmd_status, argparse.Namespace(json=False))
        elif choice == "2" and confirm(tr(config, "rotate_menu_confirm"), config):
            menu_call(cmd_rotate, argparse.Namespace())
        elif choice == "3":
            menu_call(cmd_dry_run, argparse.Namespace())
        elif choice == "4":
            menu_call(cmd_validate, argparse.Namespace())
        elif choice == "5":
            menu_call(cmd_doctor, argparse.Namespace())
        elif choice == "6" and confirm(tr(config, "cleanup_menu_confirm"), config):
            menu_call(cmd_cleanup, argparse.Namespace())
        elif choice == "7":
            menu_call(cmd_history, argparse.Namespace())
        elif choice == "8":
            menu_call(cmd_logs, argparse.Namespace(follow=False, lines=80))
        elif choice == "9":
            menu_call(cmd_timer, argparse.Namespace())
        elif choice == "10":
            menu_call(cmd_edit_config, argparse.Namespace())
        elif choice == "11" and confirm(tr(config, "menu_restart_timer_confirm"), config):
            menu_call(cmd_restart_timer, argparse.Namespace())
        elif choice == "12" and confirm(tr(config, "menu_disable_timer_confirm"), config):
            menu_call(cmd_disable, argparse.Namespace())
        elif choice == "13":
            menu_call(cmd_enable, argparse.Namespace())
        elif choice == "14" and confirm(tr(config, "rollback_menu_confirm"), config):
            menu_call(cmd_rollback, argparse.Namespace(ip="", restore_address=False))
        elif choice == "15":
            menu_call(cmd_watch, argparse.Namespace(interval=5, json=False))
        elif choice == "16":
            menu_call(cmd_notify_test, argparse.Namespace())
        elif choice == "17":
            menu_call(cmd_addresses, argparse.Namespace())
        elif choice == "18":
            menu_call(cmd_self_test, argparse.Namespace())
        elif choice == "19":
            menu_call(cmd_detect, argparse.Namespace(json=False))
        elif choice == "20":
            menu_call(cmd_setup, argparse.Namespace())
        elif choice == "21":
            menu_call(cmd_language, argparse.Namespace(language=None, interactive=True))
        elif choice == "0":
            return
        elif choice not in {"2", "6", "11", "12", "14"}:
            print(tr(config, "unknown_option", choice=choice))
        input(tr(config, "press_enter"))
        print()
        config = Config()


def cmd_uninstall(args):
    need_root()
    subprocess.run(["systemctl", "disable", "--now", "ipv6-rotate.timer"], check=False)
    for path in ["/etc/systemd/system/ipv6-rotate.timer", "/etc/systemd/system/ipv6-rotate.service", "/usr/local/bin/ipv6-rotate.sh", "/usr/local/bin/ipv6-rotate-cli.py", "/usr/local/bin/ipv6-rotate"]:
        try:
            Path(path).unlink()
        except FileNotFoundError:
            pass
    subprocess.run(["systemctl", "daemon-reload"], check=False)
    log(Config(), "uninstalled ipv6-rotate")


def command_groups(config):
    return COMMAND_GROUPS_RU if resolve_language(config.language) == "ru" else COMMAND_GROUPS


def command_descriptions(config):
    return COMMAND_DESCRIPTIONS_RU if resolve_language(config.language) == "ru" else COMMAND_DESCRIPTIONS


def print_main_help(short=False, config=None):
    config = config or Config()
    descriptions = command_descriptions(config)
    command_meta = "<команда>" if resolve_language(config.language) == "ru" else "<command>"
    options_meta = "[опции]" if resolve_language(config.language) == "ru" else "[options]"
    print(f"{tr(config, 'usage')}: ipv6-rotate [--dry-run] {command_meta} {options_meta}")
    print()
    print(tr(config, "cli_description"))
    if short:
        print()
        print(f"{tr(config, 'common_commands')}:")
        for name in ["status", "rotate", "dry-run", "doctor"]:
            print(f"{UI_INDENT}{name.ljust(14)} {descriptions[name]}")
        print()
        print(f"{tr(config, 'run')}: ipv6-rotate --help")
        print(f"{tr(config, 'run')}: ipv6-rotate help <command>")
        return
    print()
    print(f"{tr(config, 'global_options')}:")
    print(f"{UI_INDENT}--dry-run        {descriptions['dry-run']}")
    print(f"{UI_INDENT}-h, --help       {tr(config, 'help').lower()}")
    print()
    print(f"{tr(config, 'commands')}:")
    for group, commands in command_groups(config):
        print(f"{UI_INDENT}{group}:")
        for name, description in commands:
            print(f"{UI_INDENT}{UI_INDENT}{name.ljust(14)} {description}")
        print()
    print(f"{tr(config, 'help')}:")
    print(f"{UI_INDENT}ipv6-rotate help")
    print(f"{UI_INDENT}ipv6-rotate help <command>")
    print(f"{UI_INDENT}ipv6-rotate <command> --help")


def first_command(argv):
    for item in argv:
        if item == "--dry-run":
            continue
        if item.startswith("-"):
            continue
        return item
    return ""


def print_unknown_command(command, config=None):
    config = config or Config()
    print(tr(config, "invalid_command", command=command), file=sys.stderr)
    print(f"{tr(config, 'run')}: ipv6-rotate --help", file=sys.stderr)


def print_command_help(parser, command, config=None):
    command_parser = getattr(parser, "command_parsers", {}).get(command)
    if not command_parser:
        print_unknown_command(command, config)
        return 2
    command_parser.print_help()
    return 0


def build_parser(config=None):
    config = config or Config()
    descriptions = command_descriptions(config)
    is_ru = resolve_language(config.language) == "ru"
    formatter_class = RussianHelpFormatter if is_ru else argparse.HelpFormatter
    option_title = "опции" if is_ru else "options"
    positional_title = tr(config, "positional_arguments")
    help_text = tr(config, "help").lower()
    command_meta = "<команда>" if is_ru else "<command>"
    options_meta = "[опции]" if is_ru else "[options]"
    parser = argparse.ArgumentParser(
        prog="ipv6-rotate",
        usage=f"ipv6-rotate [--dry-run] {command_meta} {options_meta}",
        add_help=False,
        formatter_class=formatter_class,
    )
    parser._optionals.title = option_title
    parser._positionals.title = positional_title
    parser.add_argument("--dry-run", action="store_true", help=descriptions["dry-run"])
    sub = parser.add_subparsers(dest="command", metavar=command_meta)
    command_parsers = {}

    def add_command(name, **kwargs):
        description = descriptions.get(name, "")
        command_parser = sub.add_parser(
            name,
            help=description,
            description=description,
            usage=f"ipv6-rotate {name} {options_meta}",
            add_help=False,
            formatter_class=formatter_class,
            **kwargs,
        )
        command_parser._optionals.title = option_title
        command_parser._positionals.title = positional_title
        command_parser.add_argument("-h", "--help", action="help", help=help_text)
        command_parsers[name] = command_parser
        return command_parser

    add_command("rotate").set_defaults(func=cmd_rotate)
    status = add_command("status")
    status.add_argument("--json", action="store_true")
    status.add_argument("--table", action="store_true")
    status.set_defaults(func=cmd_status)
    add_command("dry-run").set_defaults(func=cmd_dry_run)
    add_command("test").set_defaults(func=cmd_test)
    detect = add_command("detect")
    detect.add_argument("--json", action="store_true")
    detect.set_defaults(func=cmd_detect)
    add_command("setup").set_defaults(func=cmd_setup)
    language = add_command("language")
    language.add_argument("language", nargs="?", choices=sorted(LANGUAGES))
    language.set_defaults(func=cmd_language)
    cleanup = add_command("cleanup")
    cleanup.add_argument("--max-old", type=int, default=None, help=tr(config, "arg_max_old"))
    cleanup.add_argument("--json", action="store_true")
    cleanup.set_defaults(func=cmd_cleanup)
    add_command("validate").set_defaults(func=cmd_validate)
    doctor = add_command("doctor")
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument("--table", action="store_true")
    doctor.set_defaults(func=cmd_doctor)
    safe_check = add_command("safe-check")
    safe_check.add_argument("--json", action="store_true")
    safe_check.add_argument("--table", action="store_true")
    safe_check.set_defaults(func=cmd_safe_check)
    healthcheck_parser = add_command("healthcheck")
    healthcheck_parser.add_argument("--mode", choices=["basic", "normal", "strict", "paranoid"], default="")
    healthcheck_parser.add_argument("--json", action="store_true")
    healthcheck_parser.set_defaults(func=cmd_healthcheck)
    add_command("addresses").set_defaults(func=cmd_addresses)
    add_command("self-test").set_defaults(func=cmd_self_test)
    history = add_command("history")
    history.add_argument("--json", action="store_true")
    history.add_argument("--table", action="store_true")
    history.set_defaults(func=cmd_history)
    timer = add_command("timer")
    timer.add_argument("timer_action", nargs="?", choices=["show", "set", "enable", "disable", "restart"], default="show")
    timer.add_argument("interval", nargs="?", help=tr(config, "arg_timer_interval"))
    timer.add_argument("--json", action="store_true")
    timer.add_argument("--table", action="store_true")
    timer.set_defaults(func=cmd_timer)
    config_cmd = add_command("config")
    config_cmd.add_argument("config_action", nargs="?", choices=["show", "set"], default="show")
    config_cmd.add_argument("key", nargs="?")
    config_cmd.add_argument("value", nargs="?")
    config_cmd.add_argument("--json", action="store_true")
    config_cmd.add_argument("--table", action="store_true")
    config_cmd.set_defaults(func=cmd_config)
    add_command("edit-config").set_defaults(func=cmd_edit_config)
    add_command("enable").set_defaults(func=cmd_enable)
    add_command("disable").set_defaults(func=cmd_disable)
    add_command("restart-timer").set_defaults(func=cmd_restart_timer)
    rollback = add_command("rollback")
    rollback.add_argument("--ip", default="", help=tr(config, "arg_rollback_ip"))
    rollback.add_argument("--restore-address", action="store_true", help=tr(config, "arg_restore_address"))
    rollback.set_defaults(func=cmd_rollback)
    add_command("emergency").set_defaults(func=cmd_emergency)
    restore_route = add_command("restore-route")
    restore_route.add_argument("--ip", default="", help=tr(config, "arg_restore_route_ip"))
    restore_route.set_defaults(func=cmd_restore_route)
    add_command("print-rescue").set_defaults(func=cmd_print_rescue)
    purge = add_command("purge")
    purge.add_argument("-y", "--yes", action="store_true", help=tr(config, "arg_purge_yes"))
    purge.set_defaults(func=cmd_purge)
    add_command("version").set_defaults(func=cmd_version)
    watch = add_command("watch")
    watch.add_argument("--interval", default=5, type=int)
    watch.add_argument("--json", action="store_true")
    watch.set_defaults(func=cmd_watch)
    add_command("notify-test").set_defaults(func=cmd_notify_test)
    logs = add_command("logs")
    logs.add_argument("-f", "--follow", action="store_true")
    logs.add_argument("-n", "--lines", default=80, type=int)
    logs.set_defaults(func=cmd_logs)
    add_command("menu").set_defaults(func=cmd_menu)
    add_command("uninstall").set_defaults(func=cmd_uninstall)
    parser.command_parsers = command_parsers
    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    config = Config()
    parser = build_parser(config)
    command = first_command(argv)
    if not argv:
        print_main_help(short=True, config=config)
        return 2
    if command == "help":
        help_args = [item for item in argv[argv.index("help") + 1:] if not item.startswith("-")]
        if not help_args:
            print_main_help(config=config)
            return 0
        return print_command_help(parser, help_args[0], config)
    if command:
        if command not in COMMAND_DESCRIPTIONS:
            print_unknown_command(command, config)
            return 2
        if any(item in {"-h", "--help"} for item in argv):
            return print_command_help(parser, command, config)
    elif any(item in {"-h", "--help"} for item in argv):
        print_main_help(config=config)
        return 0

    args = parser.parse_args(argv)
    if args.dry_run:
        return cmd_dry_run(args)
    if not getattr(args, "command", None):
        print_main_help(short=True, config=config)
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

