# IPv6 Rotate

Safe transactional IPv6 source-address rotator for Linux servers with systemd.

Безопасный транзакционный ротатор исходящего IPv6-адреса для Linux-серверов с systemd.

Language:

- [English](#english)
- [Русский](#russian)

All address examples use `2001:db8::/32`, the documentation-only IPv6 range.

<a id="english"></a>

## English

All commands below assume you are logged in as root. If you use a non-root user, prepend `sudo` to install, rotate, rollback, cleanup, config, and timer commands.

### 1. Scope

IPv6 Rotate manages only:

- IPv6 address add/change/delete
- default IPv6 route `src`
- healthchecks
- rollback
- state/history/logs
- cleanup
- systemd timer

It does not manage Docker, Xray, 3x-ui, iptables/nftables, VPN application routing, DNS records, provider routing, firewall policy, or IPv4 routing.

### 2. Requirements

- Linux server
- root access
- systemd
- iproute2: `ip`
- `python3`
- `ping`
- `curl` recommended for `strict` and `paranoid` healthchecks
- routed IPv6 `/64` from provider
- one static keep IPv6 address recommended
- console/rescue access recommended before production use

Docker is not required. pip packages are not required.

### 3. How It Works

```text
1. Read /etc/default/ipv6-rotate.
2. Detect the current default IPv6 route src.
3. Generate a new IPv6 address inside PREFIX.
4. Add it to IFACE.
5. Replace the default IPv6 route src with the new address.
6. Run the configured healthcheck.
7. On success, deprecate old rotated addresses and update state.
8. After state update, cleanup removes expired old addresses and enforces MAX_OLD_ADDRS.
9. On failure, restore the old route src and remove the new address.
```

`KEEP_ADDRS` are never removed by cleanup.

### 4. Configuration

Fresh install can read `.env`; update prefers the installed config at `/etc/default/ipv6-rotate`. Installation writes `/etc/default/ipv6-rotate`.

IPv6 Rotate manages one selected routed `/64`.

If your provider gives you a larger block such as `/48` or `/56`, choose one `/64` from it and set `PREFIX` to the first four hextets.

The tool does not manage whole provider blocks.

Do not commit `.env`. It may contain real server addresses and webhook URLs.

| Variable | Meaning | Example |
| --- | --- | --- |
| `IFACE` | public network interface | `ens3` |
| `PREFIX` | routed IPv6 `/64`, first four hextets | `2001:db8:abcd:1234` |
| `GATEWAY` | IPv6 gateway | `2001:db8:abcd:1234::1` |
| `KEEP_ADDRS` | static IPv6 addresses that must not be removed | `2001:db8:abcd:1234::2` |
| `LANGUAGE` | CLI and installer message language: `auto`, `en`, `ru` | `auto` |
| `INTERVAL` | installer-time timer interval | `10min` |
| `GRACE_SECONDS` | how long old IPv6 addresses remain valid | `1800` |
| `MAX_OLD_ADDRS` | maximum old rotated addresses to keep | `10` |
| `HEALTHCHECK_MODE` | `basic`, `normal`, `strict`, `paranoid` | `strict` |
| `HEALTHCHECK_PING6` | external IPv6 ping targets | see `example.env` |
| `HEALTHCHECK_URLS` | public IPv6 echo URLs | see `example.env` |
| `WEBHOOK_URL` | optional notification webhook | `https://example.invalid/webhook` |
| `LOG_FILE` | log file path | `/var/log/ipv6-rotate.log` |

`INTERVAL` is an installer-time value. It is used when `install.sh` writes the systemd timer. After installation, change the runtime interval with:

```bash
ipv6-rotate timer set 7min
```

The runtime timer source of truth is systemd timer/override, not `/etc/default/ipv6-rotate`.

During update, `install.sh` prefers the installed config at `/etc/default/ipv6-rotate`. This prevents an old `.env` from overwriting runtime changes made with `ipv6-rotate config` or `ipv6-rotate timer` commands.

To intentionally reinstall from `.env`, pass `--use-env`. The timer interval is preserved from the existing systemd timer unless `INTERVAL` is explicitly set in the selected config source. If a systemd timer override exists, it remains the runtime source of truth and `install.sh` prints a warning.

### 5. First-Time Install

`--no-enable-timer` is recommended for the first install. It lets you validate, dry-run, and test one manual rotation before the timer starts.

```bash
mkdir -p /root/IPv6-Rotate
git clone https://github.com/Dennitsa0-0/IPv6-Rotate.git /root/IPv6-Rotate
cd /root/IPv6-Rotate
cp example.env .env
chmod 600 .env
nano .env
bash install.sh --no-enable-timer
ipv6-rotate validate
ipv6-rotate dry-run
ipv6-rotate rotate
ipv6-rotate status
systemctl enable --now ipv6-rotate.timer
systemctl list-timers ipv6-rotate.timer --no-pager
```

The target directory must be empty. For reinstall/update, use the update section below.

### 6. Install With Auto-Detect

```bash
cd /root/IPv6-Rotate
bash install.sh --no-enable-timer
ipv6-rotate detect
ipv6-rotate setup
ipv6-rotate validate
ipv6-rotate dry-run
ipv6-rotate rotate
ipv6-rotate status
systemctl enable --now ipv6-rotate.timer
```

`detect` only prints detected values. `setup` writes `/etc/default/ipv6-rotate` after confirmation.

### 7. Install With Manual .env

```bash
cd /root/IPv6-Rotate
cp example.env .env
chmod 600 .env
nano .env
bash install.sh --no-enable-timer
ipv6-rotate validate
ipv6-rotate dry-run
```

If this is a reinstall and `/etc/default/ipv6-rotate` already exists, pass `--use-env` to intentionally apply `.env`.

Minimal server values:

```bash
IFACE="ens3"
PREFIX="2001:db8:abcd:1234"
GATEWAY="2001:db8:abcd:1234::1"
KEEP_ADDRS="2001:db8:abcd:1234::2"
LANGUAGE="auto"
INTERVAL="10min"
GRACE_SECONDS="1800"
MAX_OLD_ADDRS="10"
HEALTHCHECK_MODE="strict"
```

### 8. Update Existing Installation

```bash
cd /root/IPv6-Rotate
git pull --ff-only
python3 -m py_compile cli.py
python3 cli.py self-test
bash -n install.sh
bash -n uninstall.sh
bash -n install-ipv6-rotate.sh
bash install.sh --dry-run
bash install.sh --no-enable-timer
ipv6-rotate validate
ipv6-rotate status
systemctl enable --now ipv6-rotate.timer
```

During update, `install.sh` prefers the installed config at `/etc/default/ipv6-rotate`. This prevents an old `.env` from overwriting runtime changes made with `ipv6-rotate config` or `ipv6-rotate timer` commands. It preserves `IFACE`, `PREFIX`, `GATEWAY`, `KEEP_ADDRS`, healthcheck settings, grace period, `MAX_OLD_ADDRS`, webhook and log path.

In safe update mode, the installed config file is preserved and not rewritten.

To intentionally reinstall from `.env`, pass `--use-env`:

```bash
bash install.sh --use-env --no-enable-timer
```

The timer interval is preserved from the existing systemd timer unless `INTERVAL` is explicitly set in the selected config source. If a systemd timer override exists, it remains the runtime source of truth and `install.sh` prints a warning.

Installer messages follow `LANGUAGE=ru`, `LANGUAGE=en`, or `LANGUAGE=auto` from `.env`, `/etc/default/ipv6-rotate`, or an environment override for test runs:

```bash
LANGUAGE=ru bash install.sh --dry-run
LANGUAGE=en bash install.sh --dry-run
```

If you need to test a manual rotation after update:

```bash
ipv6-rotate rotate
echo $?
ipv6-rotate status
```

### 9. Timer Configuration

`OnBootSec=1min` means the first activation after boot or timer start. `OnUnitActiveSec=10min` means every 10 minutes after the previous service activation. `OnBootSec=1min` does not mean "every minute".

```bash
ipv6-rotate timer
ipv6-rotate timer set 7min
ipv6-rotate timer enable
ipv6-rotate timer disable
ipv6-rotate timer restart
systemctl list-timers ipv6-rotate.timer --no-pager
```

Use `ipv6-rotate timer set <interval>` after installation instead of editing `INTERVAL` in `/etc/default/ipv6-rotate`.

### 10. Grace Period And Old Addresses

`GRACE_SECONDS` controls how long old IPv6 addresses remain valid after rotation. Old addresses are deprecated with `preferred_lft 0` and `valid_lft GRACE_SECONDS`.

```text
Rotation interval: 10min
GRACE_SECONDS: 1800

New route src changes every 10 minutes.
Old addresses remain valid for about 30 minutes.
```

Check assigned global IPv6 addresses:

```bash
ip -o -6 addr show dev ens3 scope global
```

### 11. Healthcheck Modes

Recommended modes:

```text
basic    gateway ping only
normal   gateway ping + external IPv6 reachability
strict   normal + public IPv6 must match route src
paranoid strict twice, with a short delay
```

Use `HEALTHCHECK_MODE="strict"` in new configs unless you intentionally need a different mode.

### 12. Commands

```bash
ipv6-rotate help
ipv6-rotate help rotate
ipv6-rotate rotate
ipv6-rotate dry-run
ipv6-rotate rollback
ipv6-rotate rollback --restore-address
ipv6-rotate rollback --ip 2001:db8:abcd:1234::2
ipv6-rotate cleanup
ipv6-rotate cleanup --max-old 10
ipv6-rotate status
ipv6-rotate watch
ipv6-rotate doctor
ipv6-rotate safe-check
ipv6-rotate healthcheck --mode paranoid
ipv6-rotate validate
ipv6-rotate test
ipv6-rotate self-test
ipv6-rotate addresses
ipv6-rotate history
ipv6-rotate logs
ipv6-rotate logs --follow
ipv6-rotate timer
ipv6-rotate timer set 7min
ipv6-rotate timer enable
ipv6-rotate timer disable
ipv6-rotate timer restart
ipv6-rotate detect
ipv6-rotate setup
ipv6-rotate config
ipv6-rotate config set language ru
ipv6-rotate config set grace 1800
ipv6-rotate config set healthcheck strict
ipv6-rotate config set interval 7min
ipv6-rotate edit-config
ipv6-rotate language
ipv6-rotate language en
ipv6-rotate language ru
ipv6-rotate notify-test
ipv6-rotate enable
ipv6-rotate disable
ipv6-rotate restart-timer
ipv6-rotate emergency
ipv6-rotate restore-route
ipv6-rotate print-rescue
ipv6-rotate menu
ipv6-rotate version
ipv6-rotate purge
ipv6-rotate uninstall
```

Running `ipv6-rotate` without a subcommand prints help and does not rotate.

### 13. JSON Output

Plain output is the default because framed terminal tables can break after terminal resize or when pasted into logs.

```bash
ipv6-rotate status
ipv6-rotate status --table
ipv6-rotate status --json

ipv6-rotate doctor
ipv6-rotate doctor --table
ipv6-rotate doctor --json

ipv6-rotate history --json
ipv6-rotate cleanup --json
ipv6-rotate healthcheck --json
```

Use `--table` for stable terminals and `--json` for machine output.

### 14. Rollback And Recovery

```bash
ipv6-rotate rollback
ipv6-rotate rollback --ip 2001:db8:abcd:1234::2
ipv6-rotate rollback --restore-address
ipv6-rotate restore-route
ipv6-rotate emergency
ipv6-rotate print-rescue
```

`rollback` refuses to use a missing target address unless `--restore-address` is passed. `print-rescue` prints manual `ip` commands for emergency recovery. `emergency` explains safe recovery steps.

### 15. Cleanup

```bash
ipv6-rotate addresses
ipv6-rotate cleanup
ipv6-rotate cleanup --max-old 10
```

After a successful rotation, cleanup runs automatically: expired old addresses are removed and `MAX_OLD_ADDRS` is enforced. Manual cleanup is still useful after changing `GRACE_SECONDS` or `MAX_OLD_ADDRS`.

### 16. Logs And State

```text
/etc/default/ipv6-rotate
/var/lib/ipv6-rotate/state.json
/var/log/ipv6-rotate.log
/etc/systemd/system/ipv6-rotate.service
/etc/systemd/system/ipv6-rotate.timer
/etc/systemd/system/ipv6-rotate.timer.d/
```

```bash
ipv6-rotate logs
ipv6-rotate logs --follow
journalctl -u ipv6-rotate.service -u ipv6-rotate.timer --no-pager -n 100
```

### 17. Uninstall And Purge

Plain uninstall removes installed files and systemd units, including `/etc/systemd/system/ipv6-rotate.timer.d`, but keeps config/state/logs:

```bash
bash uninstall.sh
```

`--purge` also removes `/etc/default/ipv6-rotate`, `/var/lib/ipv6-rotate`, and `/var/log/ipv6-rotate.log`:

```bash
bash uninstall.sh --purge
```

### 18. Why Not Docker?

IPv6 source-address rotation changes host addresses and the host default route. A container would usually need privileged host networking to do that safely, so IPv6 Rotate is intentionally host-native and systemd-based.

### 19. Safety Notes

- Keep a known-good static IPv6 in `KEEP_ADDRS`.
- Verify provider routing and gateway reachability before enabling the timer.
- Keep console/rescue access available before production use.
- Start with `--no-enable-timer`, `validate`, `dry-run`, and one manual `rotate`.
- Do not paste production IPv6 addresses into docs or issues.

### 20. Limitations

- Requires a routed IPv6 `/64` or equivalent provider setup.
- Does not force application traffic to use IPv6.
- Does not manage IPv4 routing.
- Does not manage Docker/Xray/3x-ui routing.
- Existing long-lived TCP connections may keep using the old source address until they reconnect.
- Rotation changes the host IPv6 route source, not DNS records or provider routing.
- This is not an anonymity tool.
- Healthchecks depend on external IPv6 reachability and configured endpoints.

### 21. Troubleshooting

Timer active but no next run:

```bash
systemctl status ipv6-rotate.timer --no-pager
systemctl list-timers ipv6-rotate.timer --all --no-pager
journalctl -u ipv6-rotate.timer -u ipv6-rotate.service --no-pager -n 100
```

Public IPv6 does not match route src:

```bash
ipv6-rotate status
ip -6 route get 2001:db8::1
curl -6 -fsS https://api64.ipify.org
```

Rotation failed:

```bash
ipv6-rotate doctor
ipv6-rotate logs
ipv6-rotate rollback
ipv6-rotate print-rescue
```

Too many old addresses:

```bash
ipv6-rotate addresses
ipv6-rotate cleanup
ipv6-rotate cleanup --max-old 10
```

Terminal UI looks broken after resize:

```text
Use plain output by default.
Use --table only for stable terminals.
Run reset if the terminal is visually corrupted.
```

### 22. Exit Codes

```text
0  success
1  operation failed
2  usage error, invalid arguments, missing command, or invalid config
```

Expected examples:

```text
ipv6-rotate rotate success -> 0
ipv6-rotate rotate failed -> 1
ipv6-rotate without subcommand -> 2
invalid command -> 2
invalid args -> 2
```

### 23. Root-Required Commands

Some read-only commands may work without root, but production diagnostics are more reliable as root.

| Command | Root required | Changes network/system |
| --- | --- | --- |
| `status` | no | no |
| `doctor` | recommended | no |
| `validate` | recommended | no |
| `dry-run` | no | no |
| `rotate` | yes | yes |
| `rollback` | yes | yes |
| `cleanup` | yes | yes |
| `setup` | yes | config |
| `config set` | yes | config/systemd for interval |
| `timer set` | yes | systemd |
| `timer enable` | yes | systemd |
| `timer disable` | yes | systemd |
| `purge` | yes | config/state/logs |
| `uninstall` | yes | installed files/systemd |

### 24. Maintainer Checklist

Local:

```bash
python3 -m py_compile cli.py
python3 cli.py self-test
bash -n install.sh
bash -n uninstall.sh
bash -n install-ipv6-rotate.sh
bash install.sh --dry-run
LANGUAGE=ru bash install.sh --dry-run
LANGUAGE=en bash install.sh --dry-run
```

On a test server:

```bash
ipv6-rotate validate
ipv6-rotate dry-run
ipv6-rotate status
ipv6-rotate doctor
ipv6-rotate safe-check
systemctl list-timers ipv6-rotate.timer --no-pager
```

Manual checks:

```text
timer active/enabled
route src matches public IPv6
healthcheck OK
rollback does not use missing address unless --restore-address
cleanup does not delete KEEP_ADDRS
uninstall removes timer override directory
```

Suggested GitHub topics:

```text
ipv6
ipv6-rotator
ipv6-rotation
linux
systemd
networking
routing
source-address
healthcheck
rollback
python3
```

Suggested GitHub About description:

```text
Host-native IPv6 source-address rotator for Linux/systemd with rollback, healthchecks, cleanup, JSON output and no Docker/pip dependencies.
```

<a id="russian"></a>

## Русский

Все команды ниже предполагают, что вы работаете под root. Если вы используете обычного пользователя, добавляйте `sudo` к install, rotate, rollback, cleanup, config и timer-командам.

### 1. Зона ответственности

IPv6 Rotate управляет только:

- добавлением, изменением и удалением IPv6-адресов
- `src` в default IPv6 route
- healthchecks
- rollback
- state/history/logs
- cleanup
- systemd timer

Утилита не управляет Docker, Xray, 3x-ui, iptables/nftables, маршрутизацией VPN-приложений, DNS-записями, маршрутизацией у провайдера, firewall policy или IPv4 routing.

### 2. Требования

- Linux server
- root access
- systemd
- iproute2: `ip`
- `python3`
- `ping`
- `curl` рекомендуется для `strict` и `paranoid` healthchecks
- маршрутизированный IPv6 `/64` от провайдера
- рекомендуется один статический keep IPv6 address
- перед production рекомендуется console/rescue access

Docker не требуется. pip-пакеты не требуются.

### 3. Как это работает

```text
1. Прочитать /etc/default/ipv6-rotate.
2. Определить текущий default IPv6 route src.
3. Сгенерировать новый IPv6 внутри PREFIX.
4. Добавить его на IFACE.
5. Заменить default IPv6 route src на новый адрес.
6. Выполнить настроенный healthcheck.
7. При успехе устарить старые ротационные адреса и обновить state.
8. После state update cleanup удаляет истекшие старые адреса и применяет MAX_OLD_ADDRS.
9. При ошибке вернуть старый route src и удалить новый адрес.
```

`KEEP_ADDRS` никогда не удаляются cleanup-ом.

### 4. Конфигурация

Первая установка может читать `.env`; обновление предпочитает установленный конфиг `/etc/default/ipv6-rotate`. Установка пишет `/etc/default/ipv6-rotate`.

IPv6 Rotate управляет одним выбранным маршрутизированным `/64`.

Если провайдер выдал более крупный блок, например `/48` или `/56`, выберите один `/64` внутри него и укажите `PREFIX` как первые четыре hextet.

Утилита не управляет целыми provider blocks.

Не коммитьте `.env`. Он может содержать реальные адреса сервера и webhook URL.

| Переменная | Значение | Пример |
| --- | --- | --- |
| `IFACE` | публичный сетевой интерфейс | `ens3` |
| `PREFIX` | маршрутизированный IPv6 `/64`, первые четыре hextet | `2001:db8:abcd:1234` |
| `GATEWAY` | IPv6-шлюз | `2001:db8:abcd:1234::1` |
| `KEEP_ADDRS` | статические IPv6, которые нельзя удалять | `2001:db8:abcd:1234::2` |
| `LANGUAGE` | язык сообщений CLI и installer: `auto`, `en`, `ru` | `auto` |
| `INTERVAL` | interval таймера на этапе установки | `10min` |
| `GRACE_SECONDS` | сколько старые IPv6 остаются действительными | `1800` |
| `MAX_OLD_ADDRS` | максимум старых ротационных адресов | `10` |
| `HEALTHCHECK_MODE` | `basic`, `normal`, `strict`, `paranoid` | `strict` |
| `HEALTHCHECK_PING6` | внешние IPv6 ping targets | см. `example.env` |
| `HEALTHCHECK_URLS` | URL для проверки публичного IPv6 | см. `example.env` |
| `WEBHOOK_URL` | необязательный webhook | `https://example.invalid/webhook` |
| `LOG_FILE` | путь к log file | `/var/log/ipv6-rotate.log` |

`INTERVAL` используется на этапе установки. `install.sh` использует его при записи systemd timer. После установки интервал меняется командой:

```bash
ipv6-rotate timer set 7min
```

Runtime-источник истины для интервала - systemd timer/override, а не `/etc/default/ipv6-rotate`.

При обновлении `install.sh` предпочитает установленный конфиг `/etc/default/ipv6-rotate`. Это не дает старому `.env` перезаписать runtime-настройки, сделанные через `ipv6-rotate config` или `ipv6-rotate timer`.

Чтобы намеренно переустановить из `.env`, передайте `--use-env`. Интервал таймера сохраняется из существующего systemd timer, если `INTERVAL` явно не задан в выбранном источнике конфига. Если существует systemd timer override, он остается runtime-источником истины, а `install.sh` выводит предупреждение.

### 5. Первая установка

`--no-enable-timer` рекомендуется для первой установки. Он позволяет выполнить `validate`, `dry-run` и одну ручную ротацию до запуска таймера.

```bash
mkdir -p /root/IPv6-Rotate
git clone https://github.com/Dennitsa0-0/IPv6-Rotate.git /root/IPv6-Rotate
cd /root/IPv6-Rotate
cp example.env .env
chmod 600 .env
nano .env
bash install.sh --no-enable-timer
ipv6-rotate validate
ipv6-rotate dry-run
ipv6-rotate rotate
ipv6-rotate status
systemctl enable --now ipv6-rotate.timer
systemctl list-timers ipv6-rotate.timer --no-pager
```

Целевая директория должна быть пустой. Для переустановки или обновления используйте соответствующий раздел ниже.

### 6. Установка через detect/setup

```bash
cd /root/IPv6-Rotate
bash install.sh --no-enable-timer
ipv6-rotate detect
ipv6-rotate setup
ipv6-rotate validate
ipv6-rotate dry-run
ipv6-rotate rotate
ipv6-rotate status
systemctl enable --now ipv6-rotate.timer
```

`detect` только показывает найденные значения. `setup` пишет `/etc/default/ipv6-rotate` после подтверждения.

### 7. Установка через .env

```bash
cd /root/IPv6-Rotate
cp example.env .env
chmod 600 .env
nano .env
bash install.sh --no-enable-timer
ipv6-rotate validate
ipv6-rotate dry-run
```

Если это переустановка и `/etc/default/ipv6-rotate` уже существует, передайте `--use-env`, чтобы намеренно применить `.env`.

Минимальные серверные значения:

```bash
IFACE="ens3"
PREFIX="2001:db8:abcd:1234"
GATEWAY="2001:db8:abcd:1234::1"
KEEP_ADDRS="2001:db8:abcd:1234::2"
LANGUAGE="auto"
INTERVAL="10min"
GRACE_SECONDS="1800"
MAX_OLD_ADDRS="10"
HEALTHCHECK_MODE="strict"
```

### 8. Обновление существующей установки

```bash
cd /root/IPv6-Rotate
git pull --ff-only
python3 -m py_compile cli.py
python3 cli.py self-test
bash -n install.sh
bash -n uninstall.sh
bash -n install-ipv6-rotate.sh
bash install.sh --dry-run
bash install.sh --no-enable-timer
ipv6-rotate validate
ipv6-rotate status
systemctl enable --now ipv6-rotate.timer
```

При обновлении `install.sh` предпочитает установленный конфиг `/etc/default/ipv6-rotate`. Это не дает старому `.env` перезаписать runtime-настройки, сделанные через `ipv6-rotate config` или `ipv6-rotate timer`. Это сохраняет `IFACE`, `PREFIX`, `GATEWAY`, `KEEP_ADDRS`, healthcheck-настройки, grace period, `MAX_OLD_ADDRS`, webhook и путь к логу.

В режиме безопасного обновления установленный конфиг сохраняется и не перезаписывается.

Чтобы намеренно переустановить из `.env`, передайте `--use-env`:

```bash
bash install.sh --use-env --no-enable-timer
```

Интервал таймера сохраняется из существующего systemd timer, если `INTERVAL` явно не задан в выбранном источнике конфига. Если существует systemd timer override, он остается runtime-источником истины, а `install.sh` выводит предупреждение.

Сообщения installer учитывают `LANGUAGE=ru`, `LANGUAGE=en` или `LANGUAGE=auto` из `.env`, `/etc/default/ipv6-rotate` или environment override для тестового запуска:

```bash
LANGUAGE=ru bash install.sh --dry-run
LANGUAGE=en bash install.sh --dry-run
```

Если нужно протестировать ручную ротацию после update:

```bash
ipv6-rotate rotate
echo $?
ipv6-rotate status
```

### 9. Настройка таймера

`OnBootSec=1min` означает первый запуск после boot/start timer. `OnUnitActiveSec=10min` означает повторный запуск каждые 10 минут после предыдущей активации service. `OnBootSec=1min` не означает "каждую минуту".

```bash
ipv6-rotate timer
ipv6-rotate timer set 7min
ipv6-rotate timer enable
ipv6-rotate timer disable
ipv6-rotate timer restart
systemctl list-timers ipv6-rotate.timer --no-pager
```

После установки используйте `ipv6-rotate timer set <interval>`, а не редактирование `INTERVAL` в `/etc/default/ipv6-rotate`.

### 10. Grace period и старые адреса

`GRACE_SECONDS` задает, как долго старые IPv6 остаются действительными после ротации. Старые адреса переводятся в `preferred_lft 0` и `valid_lft GRACE_SECONDS`.

```text
Rotation interval: 10min
GRACE_SECONDS: 1800

New route src changes every 10 minutes.
Old addresses remain valid for about 30 minutes.
```

Проверка назначенных global IPv6:

```bash
ip -o -6 addr show dev ens3 scope global
```

### 11. Режимы проверки

Рекомендуемые режимы:

```text
basic    только ping gateway
normal   ping gateway + внешняя IPv6-связность
strict   normal + публичный IPv6 должен совпадать с route src
paranoid strict два раза, с короткой паузой
```

Для новых конфигов используйте `HEALTHCHECK_MODE="strict"`, если нет намеренной причины выбрать другой режим.

### 12. Команды

```bash
ipv6-rotate help
ipv6-rotate help rotate
ipv6-rotate rotate
ipv6-rotate dry-run
ipv6-rotate rollback
ipv6-rotate rollback --restore-address
ipv6-rotate rollback --ip 2001:db8:abcd:1234::2
ipv6-rotate cleanup
ipv6-rotate cleanup --max-old 10
ipv6-rotate status
ipv6-rotate watch
ipv6-rotate doctor
ipv6-rotate safe-check
ipv6-rotate healthcheck --mode paranoid
ipv6-rotate validate
ipv6-rotate test
ipv6-rotate self-test
ipv6-rotate addresses
ipv6-rotate history
ipv6-rotate logs
ipv6-rotate logs --follow
ipv6-rotate timer
ipv6-rotate timer set 7min
ipv6-rotate timer enable
ipv6-rotate timer disable
ipv6-rotate timer restart
ipv6-rotate detect
ipv6-rotate setup
ipv6-rotate config
ipv6-rotate config set language ru
ipv6-rotate config set grace 1800
ipv6-rotate config set healthcheck strict
ipv6-rotate config set interval 7min
ipv6-rotate edit-config
ipv6-rotate language
ipv6-rotate language en
ipv6-rotate language ru
ipv6-rotate notify-test
ipv6-rotate enable
ipv6-rotate disable
ipv6-rotate restart-timer
ipv6-rotate emergency
ipv6-rotate restore-route
ipv6-rotate print-rescue
ipv6-rotate menu
ipv6-rotate version
ipv6-rotate purge
ipv6-rotate uninstall
```

Запуск `ipv6-rotate` без подкоманды показывает help и не запускает ротацию.

### 13. JSON-вывод

Plain output используется по умолчанию, потому что framed terminal tables могут ломаться после resize терминала или при вставке в логи.

```bash
ipv6-rotate status
ipv6-rotate status --table
ipv6-rotate status --json

ipv6-rotate doctor
ipv6-rotate doctor --table
ipv6-rotate doctor --json

ipv6-rotate history --json
ipv6-rotate cleanup --json
ipv6-rotate healthcheck --json
```

Используйте `--table` для стабильных терминалов и `--json` для машинного вывода.

### 14. Rollback и восстановление

```bash
ipv6-rotate rollback
ipv6-rotate rollback --ip 2001:db8:abcd:1234::2
ipv6-rotate rollback --restore-address
ipv6-rotate restore-route
ipv6-rotate emergency
ipv6-rotate print-rescue
```

`rollback` отказывается использовать отсутствующий target address, если не указан `--restore-address`. `print-rescue` печатает ручные `ip` commands для emergency recovery. `emergency` объясняет безопасные шаги восстановления.

### 15. Очистка старых IPv6

```bash
ipv6-rotate addresses
ipv6-rotate cleanup
ipv6-rotate cleanup --max-old 10
```

После успешной ротации cleanup запускается автоматически: истекшие старые адреса удаляются, а `MAX_OLD_ADDRS` применяется. Ручной cleanup полезен после изменения `GRACE_SECONDS` или `MAX_OLD_ADDRS`.

### 16. Логи и state

```text
/etc/default/ipv6-rotate
/var/lib/ipv6-rotate/state.json
/var/log/ipv6-rotate.log
/etc/systemd/system/ipv6-rotate.service
/etc/systemd/system/ipv6-rotate.timer
/etc/systemd/system/ipv6-rotate.timer.d/
```

```bash
ipv6-rotate logs
ipv6-rotate logs --follow
journalctl -u ipv6-rotate.service -u ipv6-rotate.timer --no-pager -n 100
```

### 17. Удаление и purge

Обычное удаление убирает установленные файлы и systemd units, включая `/etc/systemd/system/ipv6-rotate.timer.d`, но сохраняет config/state/logs:

```bash
bash uninstall.sh
```

`--purge` также удаляет `/etc/default/ipv6-rotate`, `/var/lib/ipv6-rotate` и `/var/log/ipv6-rotate.log`:

```bash
bash uninstall.sh --purge
```

### 18. Почему не Docker?

Ротация исходящего IPv6 меняет адреса и default route на хосте. Контейнеру для этого обычно все равно нужен privileged host networking, поэтому IPv6 Rotate сделан host-native и systemd-based.

### 19. Замечания по безопасности

- Держите известный рабочий статический IPv6 в `KEEP_ADDRS`.
- Проверьте маршрутизацию провайдера и gateway до включения timer.
- Перед production держите доступным console/rescue access.
- Начинайте с `--no-enable-timer`, `validate`, `dry-run` и одной ручной `rotate`.
- Не публикуйте production IPv6-адреса в docs или issues.

### 20. Ограничения

- Требуется маршрутизированный IPv6 `/64` или эквивалентная настройка у провайдера.
- Утилита не заставляет приложения использовать IPv6.
- Утилита не управляет IPv4 routing.
- Утилита не управляет Docker/Xray/3x-ui routing.
- Уже открытые TCP-соединения могут продолжать использовать старый source address до переподключения.
- Ротация меняет host IPv6 route src, а не DNS-записи или маршрутизацию у провайдера.
- Это не инструмент анонимности.
- Healthcheck зависит от внешней IPv6-доступности и настроенных endpoints.

### 21. Диагностика проблем

Timer active, но нет следующего запуска:

```bash
systemctl status ipv6-rotate.timer --no-pager
systemctl list-timers ipv6-rotate.timer --all --no-pager
journalctl -u ipv6-rotate.timer -u ipv6-rotate.service --no-pager -n 100
```

Public IPv6 не совпадает с route src:

```bash
ipv6-rotate status
ip -6 route get 2001:db8::1
curl -6 -fsS https://api64.ipify.org
```

Rotation failed:

```bash
ipv6-rotate doctor
ipv6-rotate logs
ipv6-rotate rollback
ipv6-rotate print-rescue
```

Слишком много старых адресов:

```bash
ipv6-rotate addresses
ipv6-rotate cleanup
ipv6-rotate cleanup --max-old 10
```

Terminal UI выглядит сломанным после resize:

```text
Use plain output by default.
Use --table only for stable terminals.
Run reset if the terminal is visually corrupted.
```

### 22. Коды выхода

```text
0  success
1  operation failed
2  usage error, invalid arguments, missing command, or invalid config
```

Ожидаемые примеры:

```text
ipv6-rotate rotate success -> 0
ipv6-rotate rotate failed -> 1
ipv6-rotate without subcommand -> 2
invalid command -> 2
invalid args -> 2
```

### 23. Команды, требующие root

Некоторые read-only команды могут работать без root, но production diagnostics надежнее запускать под root.

| Команда | Нужен root | Меняет network/system |
| --- | --- | --- |
| `status` | no | no |
| `doctor` | recommended | no |
| `validate` | recommended | no |
| `dry-run` | no | no |
| `rotate` | yes | yes |
| `rollback` | yes | yes |
| `cleanup` | yes | yes |
| `setup` | yes | config |
| `config set` | yes | config/systemd for interval |
| `timer set` | yes | systemd |
| `timer enable` | yes | systemd |
| `timer disable` | yes | systemd |
| `purge` | yes | config/state/logs |
| `uninstall` | yes | installed files/systemd |

### 24. Чеклист maintainer-а

Локально:

```bash
python3 -m py_compile cli.py
python3 cli.py self-test
bash -n install.sh
bash -n uninstall.sh
bash -n install-ipv6-rotate.sh
bash install.sh --dry-run
LANGUAGE=ru bash install.sh --dry-run
LANGUAGE=en bash install.sh --dry-run
```

На тестовом сервере:

```bash
ipv6-rotate validate
ipv6-rotate dry-run
ipv6-rotate status
ipv6-rotate doctor
ipv6-rotate safe-check
systemctl list-timers ipv6-rotate.timer --no-pager
```

Manual checks:

```text
timer active/enabled
route src matches public IPv6
healthcheck OK
rollback does not use missing address unless --restore-address
cleanup does not delete KEEP_ADDRS
uninstall removes timer override directory
```

GitHub topics:

```text
ipv6
ipv6-rotator
ipv6-rotation
linux
systemd
networking
routing
source-address
healthcheck
rollback
python3
```

GitHub About description:

```text
Host-native IPv6 source-address rotator for Linux/systemd with rollback, healthchecks, cleanup, JSON output and no Docker/pip dependencies.
```
