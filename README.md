# IPv6 Rotate

Language:

[English](#english) | [Русский](#russian)

<a id="english"></a>

## English

Safe transactional IPv6 source-address rotator for Linux servers with systemd.

All examples use `2001:db8::/32`, which is reserved for documentation and is not a real routable network.

### Scope

The rotator manages only IPv6 address add/change/delete, default IPv6 route `src`, healthchecks, rollback, state/history/logs, and the systemd timer. It does not manage Xray, 3x-ui, Docker, iptables, Telegram bots, or VPN application routing.

The intended installation model is host-native systemd with no pip packages required.

### Features

- Python 3 CLI as the only runtime backend
- no pip packages required
- flat repository structure: `cli.py` and `ipv6-rotate` live in the project root
- shell only for `install.sh` and `uninstall.sh`
- no default rotate on empty command; `ipv6-rotate` prints help
- global `--dry-run` that never changes the network
- retry when a generated IPv6 already exists
- state tracks every deprecated address for later cleanup
- healthcheck modes: `strict`, `external-only`, `route-only`
- safe rollback that refuses missing addresses unless `--restore-address` is set
- English/Russian CLI text via `LANGUAGE=auto|en|ru`
- safe `detect` and interactive `setup` for IPv6 config discovery
- `addresses`, `self-test`, `doctor`, `watch`, and `notify-test`

### Project Structure

```text
cli.py
ipv6-rotate
install.sh
install-ipv6-rotate.sh
uninstall.sh
ipv6-rotate.service
ipv6-rotate.timer
example.env
.gitignore
```

### Configuration

| Variable | Meaning | Example |
| --- | --- | --- |
| `PREFIX` | IPv6 `/64` prefix, first 4 hextets only | `2001:db8:abcd:1234` |
| `IFACE` | Public network interface | `ens3`, `eth0`, `enp1s0` |
| `GATEWAY` | IPv6 gateway | `2001:db8:abcd:1234::1` |
| `KEEP_ADDRS` | Static IPv6 addresses that must never be deleted | `2001:db8:abcd:1234::2` |
| `LANGUAGE` | CLI language: `auto`, `en`, or `ru` | `auto` |
| `INTERVAL` | systemd timer interval | `10min`, `30min`, `1h` |
| `GRACE_SECONDS` | How long old addresses stay valid | `1800` |
| `HEALTHCHECK_MODE` | `strict`, `external-only`, or `route-only` | `strict` |
| `WEBHOOK_URL` | Optional failure/test notification webhook | `https://example.invalid/webhook` |

`strict` requires gateway ping and one external ping/curl check. `external-only` skips gateway ping. `route-only` only verifies that route src points to an address assigned on the interface.

### Install

```bash
cp example.env .env
nano .env
bash install.sh
```

Compatibility entrypoint:

```bash
bash install-ipv6-rotate.sh
```

The installer writes `/etc/default/ipv6-rotate`, installs `/usr/local/bin/ipv6-rotate`, installs `/usr/local/bin/ipv6-rotate-cli.py`, and installs the systemd units. If `PREFIX`, `IFACE`, `GATEWAY`, and `KEEP_ADDRS` are complete, it runs `ipv6-rotate validate` and enables the timer only when validation succeeds. If configuration is incomplete or validation fails, it leaves the timer disabled and prints the setup commands:

```bash
sudo ipv6-rotate setup
sudo ipv6-rotate validate
sudo systemctl enable --now ipv6-rotate.timer
```

### Commands

```bash
ipv6-rotate
ipv6-rotate help
ipv6-rotate help rotate
ipv6-rotate rotate --help
ipv6-rotate --dry-run
ipv6-rotate rotate
ipv6-rotate dry-run
ipv6-rotate status
ipv6-rotate status --json
ipv6-rotate detect
ipv6-rotate detect --json
ipv6-rotate setup
ipv6-rotate language
ipv6-rotate language ru
ipv6-rotate language en
ipv6-rotate addresses
ipv6-rotate watch
ipv6-rotate watch --interval 5
ipv6-rotate watch --json
ipv6-rotate test
ipv6-rotate validate
ipv6-rotate doctor
ipv6-rotate self-test
ipv6-rotate cleanup
ipv6-rotate history
ipv6-rotate logs
ipv6-rotate logs --follow
ipv6-rotate timer
ipv6-rotate config
ipv6-rotate edit-config
ipv6-rotate restart-timer
ipv6-rotate disable
ipv6-rotate enable
ipv6-rotate rollback
ipv6-rotate rollback --restore-address
ipv6-rotate rollback --ip 2001:db8:abcd:1234::2
ipv6-rotate notify-test
ipv6-rotate version
ipv6-rotate menu
ipv6-rotate purge
ipv6-rotate uninstall
```

`ipv6-rotate` without a subcommand prints help and exits with code `2`. It does not rotate.

Use `ipv6-rotate help` for the full command list, `ipv6-rotate help <command>` for command-specific help, or `ipv6-rotate <command> --help`.

`status --json` is for machine monitoring. `watch --json` is only a live terminal view; do not parse it from monitoring scripts.

`detect` only prints the detected IPv6 configuration. `setup` is interactive, requires root, and writes `/etc/default/ipv6-rotate` only after confirmation.

Commands, JSON keys, env variable names, state files, and systemd unit names stay English and stable. `LANGUAGE` only changes human-facing CLI text.

`addresses` shows the IPv6 addresses from `PREFIX` that are actually assigned to `IFACE`, including role and lifetime.

`rollback` refuses to use a target address that is not assigned to the interface. Use `rollback --restore-address` only when you intentionally want to add the old address back.

### Rotation Logic

```text
1. Remember current source IPv6 and default route.
2. Generate a new IPv6 address.
3. Try to add it to the interface.
4. If the address already exists or add fails, generate another one and retry.
5. Set default route src to the new IPv6.
6. Run the configured healthcheck mode.
7. If healthcheck passes, deprecate old rotated addresses and record all of them in state.
8. If healthcheck fails, restore the old route and remove the new address.
```

Old addresses are not deleted immediately. They are changed to:

```bash
preferred_lft 0 valid_lft "$GRACE_SECONDS"
```

`cleanup` removes deprecated addresses after the grace period.

### Menu

```text
IPv6 Rotate Manager

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
```

Dangerous menu actions ask for confirmation: rotate, cleanup, restart timer, disable timer, and rollback.

### Uninstall And Purge

Purge before uninstall if you want to use the CLI command:

```bash
ipv6-rotate purge
ipv6-rotate uninstall
```

Or use the shell script after/before command removal:

```bash
bash uninstall.sh --purge
```

Plain uninstall keeps config, state, logs, and already-added IPv6 addresses:

```bash
bash uninstall.sh
```

### Safety Notes

Before production use, make sure you have console or rescue access, a known-good static IPv6 in `KEEP_ADDRS`, a working IPv6 gateway, and a way to reconnect if network config is wrong.

<a id="russian"></a>

## Русский

Безопасный транзакционный ротатор исходящего IPv6-адреса для Linux-серверов с systemd.

Все примеры используют `2001:db8::/32`. Это документационный диапазон, а не реальная маршрутизируемая сеть.

### Зона ответственности

Ротатор управляет только добавлением, изменением и удалением IPv6-адресов, исходным адресом `src` в default IPv6 route, проверками связи, rollback, state/history/logs и systemd-таймером. Он не управляет Xray, 3x-ui, Docker, iptables, Telegram-ботами или маршрутизацией VPN-приложений.

Основной сценарий установки - host-native systemd, без pip-пакетов.

### Возможности

- основной runtime только Python 3 CLI
- pip-пакеты не нужны
- плоская структура: `cli.py` и `ipv6-rotate` лежат в корне проекта
- bash только для `install.sh` и `uninstall.sh`
- запуск без команды показывает справку и не меняет сеть
- глобальный `--dry-run`, который ничего не меняет
- повторная попытка, если сгенерированный IPv6 уже занят
- state хранит все устаревшие адреса для `cleanup`
- режимы healthcheck: `strict`, `external-only`, `route-only`
- безопасный rollback: адрес должен реально быть на интерфейсе, иначе нужен `--restore-address`
- русский и английский текст CLI через `LANGUAGE=auto|en|ru`
- безопасные команды `detect` и `setup` для поиска IPv6-конфигурации
- команды `addresses`, `self-test`, `doctor`, `watch`, `notify-test`

### Структура проекта

```text
cli.py
ipv6-rotate
install.sh
install-ipv6-rotate.sh
uninstall.sh
ipv6-rotate.service
ipv6-rotate.timer
example.env
.gitignore
```

### Конфигурация

| Переменная | Значение | Пример |
| --- | --- | --- |
| `PREFIX` | IPv6-префикс `/64`, только первые 4 hextet | `2001:db8:abcd:1234` |
| `IFACE` | публичный сетевой интерфейс | `ens3`, `eth0`, `enp1s0` |
| `GATEWAY` | IPv6-шлюз | `2001:db8:abcd:1234::1` |
| `KEEP_ADDRS` | статические IPv6, которые нельзя удалять | `2001:db8:abcd:1234::2` |
| `LANGUAGE` | язык CLI: `auto`, `en` или `ru` | `auto` |
| `INTERVAL` | интервал systemd-таймера | `10min`, `30min`, `1h` |
| `GRACE_SECONDS` | сколько старые адреса остаются действительными | `1800` |
| `HEALTHCHECK_MODE` | `strict`, `external-only` или `route-only` | `strict` |
| `WEBHOOK_URL` | необязательный webhook для сбоев и тестового уведомления | `https://example.invalid/webhook` |

`strict` требует ping до шлюза и внешний ping/curl. `external-only` пропускает ping до шлюза. `route-only` проверяет только route src и наличие адреса на интерфейсе.

### Установка

```bash
cp example.env .env
nano .env
bash install.sh
```

Совместимый entrypoint:

```bash
bash install-ipv6-rotate.sh
```

Installer пишет `/etc/default/ipv6-rotate`, ставит `/usr/local/bin/ipv6-rotate`, ставит `/usr/local/bin/ipv6-rotate-cli.py` и ставит systemd units. Если `PREFIX`, `IFACE`, `GATEWAY` и `KEEP_ADDRS` заполнены, он запускает `ipv6-rotate validate` и включает таймер только при успешной проверке. Если конфигурация неполная или проверка не прошла, таймер остаётся выключенным, а installer показывает команды настройки:

```bash
sudo ipv6-rotate setup
sudo ipv6-rotate validate
sudo systemctl enable --now ipv6-rotate.timer
```

### Команды

```bash
ipv6-rotate
ipv6-rotate help
ipv6-rotate help rotate
ipv6-rotate rotate --help
ipv6-rotate --dry-run
ipv6-rotate rotate
ipv6-rotate dry-run
ipv6-rotate status
ipv6-rotate status --json
ipv6-rotate detect
ipv6-rotate detect --json
ipv6-rotate setup
ipv6-rotate language
ipv6-rotate language ru
ipv6-rotate language en
ipv6-rotate addresses
ipv6-rotate watch
ipv6-rotate watch --interval 5
ipv6-rotate watch --json
ipv6-rotate test
ipv6-rotate validate
ipv6-rotate doctor
ipv6-rotate self-test
ipv6-rotate cleanup
ipv6-rotate history
ipv6-rotate logs
ipv6-rotate logs --follow
ipv6-rotate timer
ipv6-rotate config
ipv6-rotate edit-config
ipv6-rotate restart-timer
ipv6-rotate disable
ipv6-rotate enable
ipv6-rotate rollback
ipv6-rotate rollback --restore-address
ipv6-rotate rollback --ip 2001:db8:abcd:1234::2
ipv6-rotate notify-test
ipv6-rotate version
ipv6-rotate menu
ipv6-rotate purge
ipv6-rotate uninstall
```

`ipv6-rotate` без команды показывает help и выходит с кодом `2`. Ротация не запускается.

Используйте `ipv6-rotate help` для полного списка команд, `ipv6-rotate help <command>` для справки по конкретной команде или `ipv6-rotate <command> --help`.

`status --json` нужен для машинного мониторинга. `watch --json` только для live-view в терминале; не парсите его из мониторинга.

`detect` только показывает найденную IPv6-конфигурацию. `setup` интерактивный, требует root и пишет `/etc/default/ipv6-rotate` только после подтверждения.

Команды, JSON-ключи, имена env-переменных, state-файлы и systemd unit names остаются английскими и стабильными. `LANGUAGE` меняет только человекочитаемый текст CLI.

`addresses` показывает IPv6 из `PREFIX`, которые реально назначены на `IFACE`, их роль и lifetime.

`rollback` откажется использовать адрес, которого нет на интерфейсе. `rollback --restore-address` явно добавляет старый адрес обратно.

### Логика ротации

```text
1. Запомнить текущий source IPv6 и default route.
2. Сгенерировать новый IPv6.
3. Попробовать добавить его на интерфейс.
4. Если адрес уже занят или add упал, сгенерировать другой и повторить.
5. Поставить default route src на новый IPv6.
6. Выполнить выбранный HEALTHCHECK_MODE.
7. Если проверка успешна, устарить старые ротационные адреса и записать их все в state.
8. Если проверка неуспешна, вернуть старый route и удалить новый адрес.
```

Старые адреса не удаляются сразу. Они переводятся в:

```bash
preferred_lft 0 valid_lft "$GRACE_SECONDS"
```

`cleanup` удаляет устаревшие адреса после grace period.

### Меню

```text
IPv6 Rotate Manager

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
```

Опасные пункты меню требуют подтверждения: rotate, cleanup, restart timer, disable timer и rollback.

### Удаление и purge

Если хотите чистить через CLI, делайте purge до uninstall:

```bash
ipv6-rotate purge
ipv6-rotate uninstall
```

Или используйте shell script:

```bash
bash uninstall.sh --purge
```

Обычный uninstall сохраняет config, state, logs и уже добавленные IPv6-адреса:

```bash
bash uninstall.sh
```

### Безопасность

Перед production-запуском убедитесь, что есть console или rescue-доступ, известный рабочий статический IPv6 в `KEEP_ADDRS`, рабочий IPv6-шлюз и способ переподключиться, если сетевая конфигурация неверна.
