# IPv6 Rotate

[English](README.en.md) | [Русский](README.ru.md)

Безопасный транзакционный ротатор исходящего IPv6-адреса для Linux-серверов с systemd.

Все примеры используют `2001:db8::/32`. Это документационный диапазон, а не реальная маршрутизируемая сеть.

## Зона ответственности

Ротатор управляет только добавлением, изменением и удалением IPv6-адресов, исходным адресом `src` в default IPv6 route, проверками связи, rollback, state/history/logs и systemd-таймером. Он не управляет Xray, 3x-ui, Docker, iptables, Telegram-ботами или маршрутизацией VPN-приложений.

Основной сценарий установки - host-native systemd, без pip-пакетов.

## Возможности

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

## Структура проекта

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

## Конфигурация

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

## Установка

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

## Команды

```bash
ipv6-rotate
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

`status --json` нужен для машинного мониторинга. `watch --json` только для live-view в терминале; не парсите его из мониторинга.

`detect` только показывает найденную IPv6-конфигурацию. `setup` интерактивный, требует root и пишет `/etc/default/ipv6-rotate` только после подтверждения.

Команды, JSON-ключи, имена env-переменных, state-файлы и systemd unit names остаются английскими и стабильными. `LANGUAGE` меняет только человекочитаемый текст CLI.

`addresses` показывает IPv6 из `PREFIX`, которые реально назначены на `IFACE`, их роль и lifetime.

`rollback` откажется использовать адрес, которого нет на интерфейсе. `rollback --restore-address` явно добавляет старый адрес обратно.

## Логика ротации

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

## Меню

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

## Удаление и purge

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

## Безопасность

Перед production-запуском убедитесь, что есть console или rescue-доступ, известный рабочий статический IPv6 в `KEEP_ADDRS`, рабочий IPv6-шлюз и способ переподключиться, если сетевая конфигурация неверна)
