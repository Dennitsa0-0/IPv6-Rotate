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
VERSION = "0.4.0"
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
    },
    "ru": {
        "active": "активен",
        "addresses_title": "IPv6-адреса",
        "all_present": "все назначены",
        "auto": "авто",
        "cancel": "Отмена",
        "cancelled": "Отменено.",
        "change_values": "Изменить вручную",
        "check": "Проверка",
        "choose_option": "Выберите пункт: ",
        "config_title": "Конфигурация IPv6 Rotate",
        "continue": "Продолжить? [y/N] ",
        "current": "текущий",
        "current_route_src": "Текущий route src",
        "default_route": "Default route",
        "details": "Детали",
        "detected_title": "Найдена IPv6-конфигурация",
        "doctor_title": "Диагностика",
        "enabled": "Включен",
        "external_check": "Внешняя проверка",
        "external_ipv6": "Внешний IPv6",
        "gateway": "Gateway",
        "gateway_ping": "Ping gateway",
        "grace_seconds": "Задержка удаления, сек",
        "health": "Состояние",
        "healthcheck": "Проверка связи",
        "healthcheck_mode": "Режим проверки",
        "interface": "Интерфейс",
        "keep_address": "Не удалять адрес",
        "keep_addresses": "Не удалять адреса",
        "language": "Язык",
        "last_error": "Последняя ошибка",
        "last_rotation": "Последняя ротация",
        "last_trigger": "Последний запуск",
        "log_file": "Файл лога",
        "manual_prompt": "Оставьте пустым, чтобы сохранить текущее значение.",
        "missing": "не задано",
        "next_rotation": "Следующая ротация",
        "no_addresses": "На {iface} нет глобальных IPv6-адресов из {network}",
        "not_set": "не задан",
        "old_kept_addresses": "Старые сохраненные адреса",
        "press_enter": "\nНажмите Enter, чтобы продолжить... ",
        "prefix": "Prefix",
        "public_ipv6": "Внешний IPv6",
        "result": "Результат",
        "route_src": "Route src",
        "run_validation": "Запустить проверку сейчас? [Y/n] ",
        "save_config": "Да, сохранить",
        "setup_saved": "Конфигурация сохранена в {path}",
        "show_addresses": "Показать найденные IPv6-адреса",
        "state_file": "Файл состояния",
        "status": "Статус",
        "status_title": "Статус IPv6 Rotate",
        "timer": "Таймер",
        "timer_active": "Таймер активен",
        "timer_title": "Таймер IPv6 Rotate",
        "unknown": "неизвестно",
        "unknown_option": "Неизвестный пункт: {choice}",
        "use_config": "Использовать эту конфигурацию?",
        "validation_title": "Проверка",
        "webhook": "Webhook",
    },
}


def parse_env_file(path):
    values = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
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


def need_root():
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        raise SystemExit("ERROR: run as root")


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
        usage_error("PREFIX is not set, example: PREFIX='2001:db8:abcd:1234'")
    if config.healthcheck_mode not in HEALTHCHECK_MODES:
        usage_error(f"HEALTHCHECK_MODE must be one of: {', '.join(sorted(HEALTHCHECK_MODES))}")
    if not config.keep_list:
        usage_error("KEEP_ADDRS is empty. Run ipv6-rotate setup or set KEEP_ADDRS explicitly.")


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
        usage_error("IFACE is not set and could not be auto-detected")
    if not config.gateway:
        usage_error("GATEWAY is not set and could not be auto-detected")


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
        usage_error("IFACE is not set and could not be auto-detected")
    if not config.gateway:
        usage_error("GATEWAY is not set and could not be auto-detected")

    details = global_address_details(config)
    route_src = default_src()
    if not config.prefix:
        source = route_src or (details[0]["ip"] if details else "")
        if source:
            config.prefix = prefix_from_ip(source)
    if not config.prefix:
        usage_error("PREFIX is not set and could not be auto-detected")

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
        interval = set_timer_interval(value)
        print_plain_kv([("Rotation interval", interval), ("Override", str(TIMER_OVERRIDE_FILE))])
        return
    attr = aliases.get(normalized)
    if not attr:
        usage_error(f"Unknown config key: {key}")
    if attr == "language":
        value = normalize_language(value)
    if attr == "healthcheck_mode":
        value = normalize_healthcheck_mode(value)
        if value not in HEALTHCHECK_MODES:
            usage_error("HEALTHCHECK_MODE must be one of: basic, normal, strict, paranoid")
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
    result = run(["systemctl", "list-timers", "ipv6-rotate.timer", "--no-pager", "--no-legend"])
    line = result.stdout.splitlines()[0] if result.stdout.strip() else ""
    if not line:
        return "unknown"
    parts = line.split()
    return " ".join(parts[:2]) if len(parts) >= 2 else line


def normalize_interval(value):
    value = (value or "").strip()
    if not value:
        usage_error("Interval is empty")
    if value.isdigit():
        return f"{value}s"
    allowed_suffixes = ("s", "sec", "min", "m", "h", "hour", "hours", "d", "day", "days")
    if any(value.endswith(suffix) for suffix in allowed_suffixes):
        return value
    usage_error("Interval must look like 30s, 7min, 1h, or a number of seconds")


def timer_interval():
    if not command_exists("systemctl"):
        return "unknown"
    result = run(["systemctl", "show", "ipv6-rotate.timer", "--property=OnUnitActiveSec", "--value"])
    value = result.stdout.strip()
    return value or "unknown"


def set_timer_interval(interval):
    need_root()
    interval = normalize_interval(interval)
    TIMER_OVERRIDE_DIR.mkdir(parents=True, exist_ok=True)
    TIMER_OVERRIDE_FILE.write_text(f"[Timer]\nOnUnitActiveSec=\nOnUnitActiveSec={interval}\n", encoding="utf-8")
    run(["systemctl", "daemon-reload"], check=True)
    if timer_active():
        run(["systemctl", "restart", "ipv6-rotate.timer"], check=True)
    return interval


def systemctl_timer(action):
    need_root()
    commands = {
        "enable": ["systemctl", "enable", "--now", "ipv6-rotate.timer"],
        "disable": ["systemctl", "disable", "--now", "ipv6-rotate.timer"],
        "restart": ["systemctl", "restart", "ipv6-rotate.timer"],
    }
    run(commands[action], check=True)


def timer_details():
    if not command_exists("systemctl"):
        return {"active": "unknown", "enabled": "unknown", "next": "unknown", "last": "unknown"}
    active = "yes" if timer_active() else "no"
    enabled = timer_enabled()
    result = run(["systemctl", "show", "ipv6-rotate.timer", "--property=NextElapseUSecRealtime,LastTriggerUSec,OnUnitActiveSec", "--value"])
    values = [line.strip() for line in result.stdout.splitlines()]
    return {
        "active": active,
        "enabled": enabled,
        "next": values[0] if len(values) > 0 and values[0] else timer_next(),
        "last": values[1] if len(values) > 1 and values[1] else "unknown",
        "interval": values[2] if len(values) > 2 and values[2] else timer_interval(),
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


def acquire_lock():
    try:
        import fcntl
    except ImportError:
        return None
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    fh = LOCK_FILE.open("w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Another ipv6-rotate process is already running")
    return fh


def cmd_rotate(args):
    config = Config()
    need_root()
    require_config(config)
    detect_network(config)
    lock = acquire_lock()
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
        raise SystemExit("Could not generate a non-reserved IPv6 address")
    now = int(time.time())

    print("Dry run\n")
    print("Would add:")
    print(f"  {new_ip}/64\n")
    print("Would set default route:")
    print(f"  default via {config.gateway} dev {config.iface} src {new_ip}\n")
    print("Would keep:")
    for keep in config.keep_list:
        print(f"  {keep}/64")
    if route_src:
        print(f"  {route_src}/64")

    print("\nWould deprecate:")
    deprecated = []
    for cidr in global_addresses(config):
        addr = normalize_ip(cidr)
        if ip_in_prefix(addr, config.prefix) and addr != route_src and not is_keep_addr(config, addr):
            deprecated.append(f"{addr}/64")
    print("\n".join(f"  {item}" for item in deprecated) if deprecated else "  none")

    print("\nWould remove after grace period:")
    removable = []
    for item in previous_items():
        ip = item.get("ip", "")
        deprecated_at = int(item.get("deprecated_at") or item.get("created_at") or now)
        if ip and now - deprecated_at >= config.grace_seconds:
            removable.append(f"{ip}/64")
    print("\n".join(f"  {item}" for item in removable) if removable else "  none")


def cmd_cleanup(args):
    config = Config()
    need_root()
    require_config(config)
    detect_network(config)
    lock = acquire_lock()
    removed = cleanup_old_addresses(config, getattr(args, "max_old", None))
    if wants_json(args):
        print_records_json({"removed": removed, "removed_count": len(removed)})
    else:
        print_plain_kv([("Removed", len(removed)), ("Max old addresses", getattr(args, "max_old", None) if getattr(args, "max_old", None) is not None else config.max_old_addrs)])
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
        usage_error("Mode must be one of: basic, normal, strict, paranoid")
    config.healthcheck_mode = mode
    source = default_src()
    ok = healthcheck(config, source)
    payload = {"mode": mode, "route_src": source or "unknown", "ok": ok}
    if wants_json(args):
        print_records_json(payload)
    else:
        print_plain_kv([("Healthcheck mode", mode), ("Route src", source or "unknown"), ("Result", "OK" if ok else "FAIL")])
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
                        print(f"Validation failed with exit code {exc.code}.")
            print()
            print("Next commands:")
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
    if not getattr(args, "language", None):
        table_kv(tr(config, "language"), [
            ("LANGUAGE", config.language),
            ("Resolved", resolve_language(config.language)),
            ("Config file", str(CONFIG_FILE)),
        ])
        return
    language = normalize_language(args.language)
    if language != args.language:
        raise SystemExit("LANGUAGE must be one of: auto, en, ru")
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
        ("Interface", config.iface),
        ("Prefix", str(prefix_network(config.prefix))),
        ("Gateway", config.gateway),
        ("Healthcheck mode", config.healthcheck_mode),
        ("Current route src", route_src or "unknown"),
        ("Public IPv6", public_ip),
        ("Keep addresses", len(config.keep_list)),
        ("Old addresses", f"{len(state.get('previous', []))}/{config.max_old_addrs}"),
        ("Rotation interval", details.get("interval", "unknown")),
        ("Grace period", f"{config.grace_seconds}s"),
        ("Timer", "active" if timer else "inactive"),
        ("Timer enabled", details.get("enabled", "unknown")),
        ("Next rotation", details.get("next", "unknown")),
        ("Last rotation", last_rotation_summary(state)),
        ("Health", health.upper()),
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
        rows.append(ping_result("Gateway ping", ["ping", "-6", "-c", "1", "-W", "3", "-I", config.iface, config.gateway]))
    else:
        rows.append(["Gateway ping", "SKIP", config.healthcheck_mode])
    if first_host and route_src:
        rows.append(ping_result("Cloudflare IPv6 ping", ["ping", "-6", "-c", "1", "-W", "3", "-I", route_src, first_host]))
    else:
        rows.append(["Cloudflare IPv6 ping", "WARN", "no route src"])
    if public_ip == "unavailable":
        rows.append(["Public IPv6 curl", "WARN", "unavailable"])
    elif route_src and public_ip == route_src:
        rows.append(["Public IPv6 curl", "OK", "matched"])
    else:
        rows.append(["Public IPv6 curl", "OK", public_ip])
    if route_src and public_ip == route_src:
        rows.append(["Route src match", "OK", "matched"])
    elif public_ip == "unavailable":
        rows.append(["Route src match", "WARN", "public IPv6 unavailable"])
    else:
        rows.append(["Route src match", "WARN", f"route={route_src or 'unknown'} public={public_ip}"])
    print()
    table_rows(tr(config, "healthcheck"), [tr(config, "check"), tr(config, "status"), tr(config, "result")], rows)


def cmd_validate(args):
    config = Config()
    require_config(config)
    rows = []
    failed = False
    rows.append(["Running as root", "OK" if hasattr(os, "geteuid") and os.geteuid() == 0 else "FAIL", "root" if hasattr(os, "geteuid") and os.geteuid() == 0 else "not root"])
    failed = failed or rows[-1][1] == "FAIL"

    for dep in ["python3", "ip", "ping"]:
        path = shutil.which(dep)
        rows.append([f"{dep} installed", "OK" if path else "FAIL", path or "missing"])
        failed = failed or not path
    for dep in ["curl", "systemctl", "journalctl"]:
        path = shutil.which(dep)
        rows.append([f"{dep} recommended", "OK" if path else "WARN", path or "missing"])
    for dep in ["bash", "awk", "sed"]:
        path = shutil.which(dep)
        rows.append([f"{dep} installer-only", "OK" if path else "WARN", path or "missing"])

    try:
        network = prefix_network(config.prefix)
        rows.append(["Prefix format", "OK", str(network)])
    except Exception:
        rows.append(["Prefix format", "FAIL", "invalid PREFIX"])
        failed = True

    mode_ok = config.healthcheck_mode in HEALTHCHECK_MODES
    rows.append(["Healthcheck mode", "OK" if mode_ok else "FAIL", config.healthcheck_mode])
    failed = failed or not mode_ok

    try:
        detect_network(config)
        rows.append(["Network detected", "OK", f"{config.iface} via {config.gateway}"])
    except SystemExit as exc:
        rows.append(["Network detected", "FAIL", str(exc)])
        failed = True

    iface_ok = bool(config.iface) and run(["ip", "link", "show", "dev", config.iface]).returncode == 0
    rows.append(["Interface exists", "OK" if iface_ok else "FAIL", config.iface or "missing"])
    failed = failed or not iface_ok

    keep_ok = True
    for keep in config.keep_list:
        keep_ok = keep_ok and ip_in_prefix(keep, config.prefix)
    rows.append(["KEEP_ADDRS in prefix", "OK" if keep_ok else "FAIL", f"{len(config.keep_list)} address(es)"])
    failed = failed or not keep_ok

    if iface_ok:
        present = {normalize_ip(cidr) for cidr in global_addresses(config)}
        missing_keep = [keep for keep in config.keep_list if keep not in present]
        rows.append([
            "KEEP_ADDRS assigned",
            "OK" if not missing_keep else "FAIL",
            "all present" if not missing_keep else ", ".join(missing_keep),
        ])
        failed = failed or bool(missing_keep)

    if config.iface and config.gateway and config.healthcheck_mode in {"basic", "normal", "strict", "paranoid"}:
        rows.append(["Gateway reachable", "OK" if gateway_ping_ok(config) else "WARN", config.gateway])
    else:
        rows.append(["Gateway reachable", "SKIP", config.healthcheck_mode if config.healthcheck_mode not in {"basic", "normal", "strict", "paranoid"} else "IFACE/GATEWAY missing"])

    timer_found = command_exists("systemctl") and run(["systemctl", "list-unit-files", "ipv6-rotate.timer"]).returncode == 0
    rows.append(["systemd timer installed", "OK" if timer_found else "WARN", "ipv6-rotate.timer" if timer_found else "not found"])
    table_rows(tr(config, "validation_title"), [tr(config, "check"), tr(config, "status"), tr(config, "details")], rows)
    raise SystemExit(1 if failed else 0)


def cmd_doctor(args):
    config = Config()
    require_config(config)
    rows = []
    failed = False

    try:
        detect_network(config)
        rows.append(["Config", "OK", f"{config.iface} via {config.gateway}"])
    except SystemExit as exc:
        rows.append(["Config", "FAIL", str(exc)])
        failed = True

    rows.append(["Healthcheck mode", "OK" if config.healthcheck_mode in HEALTHCHECK_MODES else "FAIL", config.healthcheck_mode])
    failed = failed or config.healthcheck_mode not in HEALTHCHECK_MODES

    for dep in ["ip", "ping", "curl", "systemctl"]:
        path = shutil.which(dep)
        status = "OK" if path else ("WARN" if dep in {"curl", "systemctl"} else "FAIL")
        rows.append([f"Command {dep}", status, path or "missing"])
        failed = failed or status == "FAIL"

    route = default_route() if command_exists("ip") else ""
    route_src = default_src() if command_exists("ip") else ""
    rows.append(["Default route", "OK" if route else "FAIL", route or "missing"])
    rows.append(["Route src", "OK" if route_src else "WARN", route_src or "unknown"])
    failed = failed or not route

    if config.iface and command_exists("ip"):
        addrs = [normalize_ip(cidr) for cidr in global_addresses(config) if ip_in_prefix(normalize_ip(cidr), config.prefix)]
        rows.append(["Rotated prefix addrs", "OK" if addrs else "WARN", str(len(addrs))])

    if config.iface and config.gateway and config.healthcheck_mode in {"basic", "normal", "strict", "paranoid"}:
        rows.append(["Gateway ping", "OK" if gateway_ping_ok(config) else "WARN", config.gateway])
    elif config.healthcheck_mode not in {"basic", "normal", "strict", "paranoid"}:
        rows.append(["Gateway ping", "SKIP", config.healthcheck_mode])

    if route_src:
        external = external_check_ok(config, route_src)
        rows.append(["External IPv6", "OK" if external else "WARN", "ping/curl via route src"])

    state = load_state()
    last_error = state.get("last_error")
    rows.append(["Timer active", "OK" if timer_active() else "WARN", "active" if timer_active() else "inactive"])
    rows.append(["Next rotation", "INFO", timer_next()])
    rows.append(["Last rotation", "INFO", last_rotation_summary(state)])
    rows.append(["Last error", "WARN" if last_error else "OK", json.dumps(last_error) if last_error else "none"])
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
            usage_error("Usage: ipv6-rotate timer set 7min")
        interval = set_timer_interval(args.interval)
        print_plain_kv([("Rotation interval", interval), ("Override", str(TIMER_OVERRIDE_FILE))])
        return
    if action in {"enable", "disable", "restart"}:
        systemctl_timer(action)
        print(f"Timer {action}: ok")
        return
    pairs = [
        ("Active", details.get("active", "unknown")),
        (tr(config, "enabled"), details.get("enabled", "unknown")),
        (tr(config, "next_rotation"), details.get("next", "unknown")),
        (tr(config, "last_trigger"), details.get("last", "unknown")),
        ("Interval", details.get("interval", "unknown")),
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
            usage_error("Usage: ipv6-rotate config set <key> <value>")
        config_set(args.key, args.value)
        return
    pairs = [
        ("Config file", str(CONFIG_FILE)),
        (tr(config, "interface"), config.iface or tr(config, "auto")),
        (tr(config, "prefix"), config.prefix or tr(config, "missing")),
        (tr(config, "gateway"), config.gateway or tr(config, "auto")),
        (tr(config, "keep_addresses"), config.keep_addrs or tr(config, "auto")),
        (tr(config, "language"), config.language),
        (tr(config, "grace_seconds"), str(config.grace_seconds)),
        ("Max old addresses", str(config.max_old_addrs)),
        (tr(config, "healthcheck_mode"), config.healthcheck_mode),
        ("Ping checks", config.healthcheck_ping6),
        ("URL checks", config.healthcheck_urls),
        (tr(config, "webhook"), "set" if config.webhook_url else tr(config, "not_set")),
        (tr(config, "log_file"), str(config.log_file)),
        (tr(config, "state_file"), str(STATE_FILE)),
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
    need_root()
    require_config(config)
    detect_network(config)
    state = load_state()
    target = rollback_target(args, state)
    if not target:
        raise SystemExit(f"No previous/current IPv6 in {STATE_FILE}")
    if not ip_in_prefix(target, config.prefix):
        raise SystemExit(f"Rollback target is outside PREFIX: {target}")
    if not address_exists(config, target):
        if not getattr(args, "restore_address", False):
            raise SystemExit(f"Rollback target is not assigned to {config.iface}: {target}. Use --restore-address to add it back.")
        log(config, f"rollback: restoring missing IPv6 address {target}/64 on {config.iface}")
        result = run(["ip", "-6", "addr", "add", f"{target}/64", "dev", config.iface])
        if result.returncode != 0:
            raise SystemExit(result.stderr.strip() or f"failed to restore IPv6 address {target}")
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
        print("# No rescue IPv6 found in state or KEEP_ADDRS")
        print(f"# ip -6 route replace default via {config.gateway} dev {config.iface} src <IPv6>")


def cmd_print_rescue(args):
    config = Config()
    require_config(config)
    detect_network(config)
    print_rescue_commands(config, rescue_target(config))


def cmd_restore_route(args):
    config = Config()
    need_root()
    require_config(config)
    detect_network(config)
    target = getattr(args, "ip", "") or rescue_target(config)
    if not target:
        raise SystemExit("No route source available")
    target = normalize_ip(getattr(args, "ip", "") or rescue_target(config))
    run(["ip", "-6", "route", "replace", "default", "via", config.gateway, "dev", config.iface, "src", target], check=True)
    print_plain_kv([("Route src", target), ("Result", "OK")])


def cmd_emergency(args):
    config = Config()
    print("Emergency rescue commands:")
    try:
        require_config(config)
        detect_network(config)
        print_rescue_commands(config, rescue_target(config))
    except SystemExit as exc:
        print(f"# Config is incomplete: {exc}")
        print("# Run: ip -6 route show default")
        print("# Run: ip -o -6 addr show scope global")


def safe_checks(config):
    state = load_state()
    route_src = default_src()
    public_ip = public_ipv6(config)
    keep_present = all(address_exists(config, keep) for keep in config.keep_list)
    last = state.get("last_rotation", {})
    old_count = len(state.get("previous", []))
    checks = [
        ("timer active", timer_active(), "active" if timer_active() else "inactive"),
        ("timer enabled", timer_enabled() in {"enabled", "static"}, timer_enabled()),
        ("route src matches public IPv6", bool(route_src and public_ip == route_src), f"route={route_src or 'unknown'} public={public_ip}"),
        ("gateway reachable", gateway_ping_ok(config), config.gateway),
        ("external IPv6 reachable", external_check_ok(config, route_src) if route_src else False, route_src or "no route src"),
        ("keep address assigned", keep_present, "all present" if keep_present else "missing"),
        ("old addresses count acceptable", old_count <= config.max_old_addrs, f"{old_count}/{config.max_old_addrs}"),
        ("last rotation success", last.get("status", "unknown") in {"success", "unknown"}, last_rotation_summary(state)),
        ("next rotation scheduled", timer_next() != "unknown", timer_next()),
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
        table_rows("Safe check", ["Check", "Status", "Details"], [[name, "OK" if ok else "FAIL", details] for name, ok, details in checks])
        print()
        print(f"Result: {'SAFE' if not failed else 'UNSAFE'}")
    else:
        for name, ok, details in checks:
            print(f"{'OK' if ok else 'FAIL':<5} {name}: {details}")
        print(f"Result: {'SAFE' if not failed else 'UNSAFE'}")
    raise SystemExit(0 if not failed else 1)


def cmd_purge(args):
    need_root()
    if not getattr(args, "yes", False) and not confirm("This will delete ipv6-rotate config, state, and log files."):
        print("Cancelled.")
        return
    config = Config()
    for path in [CONFIG_FILE, config.log_file]:
        try:
            path.unlink()
            print(f"Removed {path}")
        except FileNotFoundError:
            pass
    shutil.rmtree(STATE_DIR, ignore_errors=True)
    print(f"Removed {STATE_DIR}")


def cmd_version(args):
    table_kv("IPv6 Rotate Version", [
        ("Version", VERSION),
        ("CLI path", str(Path(__file__).resolve())),
        ("Config file", str(CONFIG_FILE)),
        ("State file", str(STATE_FILE)),
    ])


def cmd_notify_test(args):
    config = Config()
    if not config.webhook_url:
        raise SystemExit("WEBHOOK_URL is not set")
    if not command_exists("curl"):
        raise SystemExit("curl is not installed")
    payload = json.dumps({"text": f"ipv6-rotate test notification from {socket.gethostname()}"})
    result = run(["curl", "-fsS", "--max-time", "10", "-H", "Content-Type: application/json", "-d", payload, config.webhook_url])
    if result.returncode == 0:
        print("OK: test notification sent")
        return
    raise SystemExit(result.stderr.strip() or "FAIL: test notification was not sent")


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
    table_rows(tr(config, "addresses_title"), ["IPv6", "Role", "Lifetime"], rows)


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
    check("command help", help_code == 0 and "usage: ipv6-rotate doctor [options]" in help_text, "help doctor")

    error_stderr = io.StringIO()
    with contextlib.redirect_stderr(error_stderr):
        error_code = main(["not-a-command"])
    error_text = error_stderr.getvalue()
    check("invalid command help", error_code == 2 and "Run: ipv6-rotate --help" in error_text, "clean error")

    table_rows("Self Test", ["Check", "Status", "Details"], rows)
    raise SystemExit(1 if failed else 0)


def cmd_history(args):
    state = load_state()
    rows = []
    records = []
    last = state.get("last_rotation", {})
    if state.get("current"):
        created_at = last.get("created_at")
        when = dt.datetime.fromtimestamp(int(created_at)).strftime("%F %T") if created_at else "unknown"
        rows.append([when, state["current"], last.get("status", "current")])
        records.append({"time": when, "ipv6": state["current"], "status": last.get("status", "current")})
    for item in state.get("previous", []):
        timestamp = item.get("deprecated_at") or item.get("created_at")
        when = dt.datetime.fromtimestamp(int(timestamp)).strftime("%F %T") if timestamp else "unknown"
        rows.append([when, item.get("ip", ""), "deprecated"])
        records.append({"time": when, "ipv6": item.get("ip", ""), "status": "deprecated"})
    if wants_json(args):
        print_records_json(records)
        return
    if not rows:
        print(f"No rotation history in {STATE_FILE}")
        return
    if wants_table(args):
        table_rows("Rotation history", ["Time", "IPv6", "Status"], rows)
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
    raise SystemExit(f"No journalctl and no log file: {config.log_file}")


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
  2) Запустить ротацию сейчас
  3) Проверить ротацию без изменений
  4) Проверить конфиг
  5) Диагностика
  6) Очистить старые IPv6-адреса
  7) История
  8) Логи
  9) Таймер
 10) Редактировать конфиг
 11) Перезапустить таймер
 12) Отключить таймер
 13) Включить таймер
 14) Откатиться на предыдущий IPv6
 15) Следить за статусом
 16) Тестовое уведомление
 17) Показать IPv6-адреса
 18) Самопроверка
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
        elif choice == "2" and confirm("This will add a new IPv6 address and change default IPv6 route src.", config):
            menu_call(cmd_rotate, argparse.Namespace())
        elif choice == "3":
            menu_call(cmd_dry_run, argparse.Namespace())
        elif choice == "4":
            menu_call(cmd_validate, argparse.Namespace())
        elif choice == "5":
            menu_call(cmd_doctor, argparse.Namespace())
        elif choice == "6" and confirm("This may remove old rotated IPv6 addresses.\nStatic KEEP_ADDRS will not be removed.", config):
            menu_call(cmd_cleanup, argparse.Namespace())
        elif choice == "7":
            menu_call(cmd_history, argparse.Namespace())
        elif choice == "8":
            menu_call(cmd_logs, argparse.Namespace(follow=False, lines=80))
        elif choice == "9":
            menu_call(cmd_timer, argparse.Namespace())
        elif choice == "10":
            menu_call(cmd_edit_config, argparse.Namespace())
        elif choice == "11" and confirm("This will restart ipv6-rotate.timer.", config):
            menu_call(cmd_restart_timer, argparse.Namespace())
        elif choice == "12" and confirm("This will disable ipv6-rotate.timer.", config):
            menu_call(cmd_disable, argparse.Namespace())
        elif choice == "13":
            menu_call(cmd_enable, argparse.Namespace())
        elif choice == "14" and confirm("This will change default IPv6 route src to the previous address from state.", config):
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
            menu_call(cmd_language, argparse.Namespace(language=None))
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


def print_main_help(short=False):
    print("usage: ipv6-rotate [--dry-run] <command> [options]")
    print()
    print("Safe transactional IPv6 source-address rotator for Linux servers with systemd.")
    if short:
        print()
        print("Common commands:")
        print(f"{UI_INDENT}status         show current status")
        print(f"{UI_INDENT}rotate         add a new IPv6 and switch default route src")
        print(f"{UI_INDENT}dry-run        preview rotation without changing the network")
        print(f"{UI_INDENT}doctor         run operational diagnostics")
        print()
        print("Run: ipv6-rotate --help")
        print("Run: ipv6-rotate help <command>")
        return
    print()
    print("Global options:")
    print(f"{UI_INDENT}--dry-run        preview rotate without changing anything")
    print(f"{UI_INDENT}-h, --help       show this help")
    print()
    print("Commands:")
    for group, commands in COMMAND_GROUPS:
        print(f"{UI_INDENT}{group}:")
        for name, description in commands:
            print(f"{UI_INDENT}{UI_INDENT}{name.ljust(14)} {description}")
        print()
    print("Help:")
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


def print_unknown_command(command):
    print(f"Unknown command: {command}", file=sys.stderr)
    print("Run: ipv6-rotate --help", file=sys.stderr)


def print_command_help(parser, command):
    command_parser = getattr(parser, "command_parsers", {}).get(command)
    if not command_parser:
        print_unknown_command(command)
        return 2
    command_parser.print_help()
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ipv6-rotate",
        usage="ipv6-rotate [--dry-run] <command> [options]",
        add_help=False,
    )
    parser.add_argument("--dry-run", action="store_true", help="preview rotate without changing anything")
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    command_parsers = {}

    def add_command(name, **kwargs):
        description = COMMAND_DESCRIPTIONS.get(name, "")
        command_parser = sub.add_parser(
            name,
            help=description,
            description=description,
            usage=f"ipv6-rotate {name} [options]",
            **kwargs,
        )
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
    cleanup.add_argument("--max-old", type=int, default=None, help="maximum old rotated addresses to keep")
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
    timer.add_argument("interval", nargs="?", help="interval for timer set, for example 7min")
    timer.add_argument("--json", action="store_true")
    timer.add_argument("--table", action="store_true")
    timer.set_defaults(func=cmd_timer)
    config = add_command("config")
    config.add_argument("config_action", nargs="?", choices=["show", "set"], default="show")
    config.add_argument("key", nargs="?")
    config.add_argument("value", nargs="?")
    config.add_argument("--json", action="store_true")
    config.add_argument("--table", action="store_true")
    config.set_defaults(func=cmd_config)
    add_command("edit-config").set_defaults(func=cmd_edit_config)
    add_command("enable").set_defaults(func=cmd_enable)
    add_command("disable").set_defaults(func=cmd_disable)
    add_command("restart-timer").set_defaults(func=cmd_restart_timer)
    rollback = add_command("rollback")
    rollback.add_argument("--ip", default="", help="specific IPv6 address to use as default route src")
    rollback.add_argument("--restore-address", action="store_true", help="add rollback target back to IFACE if it is missing")
    rollback.set_defaults(func=cmd_rollback)
    add_command("emergency").set_defaults(func=cmd_emergency)
    restore_route = add_command("restore-route")
    restore_route.add_argument("--ip", default="", help="IPv6 address to use as default route src")
    restore_route.set_defaults(func=cmd_restore_route)
    add_command("print-rescue").set_defaults(func=cmd_print_rescue)
    purge = add_command("purge")
    purge.add_argument("-y", "--yes", action="store_true", help="delete config/state/logs without asking")
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
    parser = build_parser()
    command = first_command(argv)
    if not argv:
        print_main_help(short=True)
        return 2
    if command == "help":
        help_args = [item for item in argv[argv.index("help") + 1:] if not item.startswith("-")]
        if not help_args:
            print_main_help()
            return 0
        return print_command_help(parser, help_args[0])
    if command:
        if command not in COMMAND_DESCRIPTIONS:
            print_unknown_command(command)
            return 2
        if any(item in {"-h", "--help"} for item in argv):
            return print_command_help(parser, command)
    elif any(item in {"-h", "--help"} for item in argv):
        print_main_help()
        return 0

    args = parser.parse_args(argv)
    if args.dry_run:
        return cmd_dry_run(args)
    if not getattr(args, "command", None):
        print_main_help(short=True)
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
