# IPv6 Rotate

[English](README.en.md) | [Russian](README.ru.md)

Safe transactional IPv6 source-address rotator for Linux servers with systemd.

All examples use `2001:db8::/32`, which is reserved for documentation and is not a real routable network.

## Scope

The rotator manages only IPv6 address add/change/delete, default IPv6 route `src`, healthchecks, rollback, state/history/logs, and the systemd timer. It does not manage Xray, 3x-ui, Docker, iptables, Telegram bots, or VPN application routing.

The intended installation model is host-native systemd with no pip packages required.

## Features

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

## Project Structure

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

## Configuration

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

## Install

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

## Commands

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

`ipv6-rotate` without a subcommand prints help and exits with code `2`. It does not rotate.

`status --json` is for machine monitoring. `watch --json` is only a live terminal view; do not parse it from monitoring scripts.

`detect` only prints the detected IPv6 configuration. `setup` is interactive, requires root, and writes `/etc/default/ipv6-rotate` only after confirmation.

Commands, JSON keys, env variable names, state files, and systemd unit names stay English and stable. `LANGUAGE` only changes human-facing CLI text.

`addresses` shows the IPv6 addresses from `PREFIX` that are actually assigned to `IFACE`, including role and lifetime.

`rollback` refuses to use a target address that is not assigned to the interface. Use `rollback --restore-address` only when you intentionally want to add the old address back.

## Rotation Logic

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

## Menu

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

## Uninstall And Purge

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

## Safety Notes

Before production use, make sure you have console or rescue access, a known-good static IPv6 in `KEEP_ADDRS`, a working IPv6 gateway, and a way to reconnect if network config is wrong.
