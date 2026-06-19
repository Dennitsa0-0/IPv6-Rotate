# Changelog

## Unreleased

- Made `sss` start a low CPU idle screen by default; use `sss game` for the playable snake.
- Changed game AUTO default to lightweight `--ai dumb`; `--ai smart` remains explicit.
- Added shared `fruit_at` hitbox lookup for eating, AI targeting, and debug checks.
- Added `--debug-ai` and `--debug-hitbox`.
- Changed ASCII snake body from `o` to `#` to avoid confusion with apples.
- Updated architecture docs to remove the old serpentine autopilot as the current design.
## 0.4.0

- Added safer local move scoring for the default `--ai safe` autopilot.
- Added safe-exit checks, open-area scoring, recent-position memory, and emergency movement.
- Added `--lookahead`, `--open-radius`, `--memory`, and `--emergency-after`.
- Changed the default installer prefix to `/usr/local` for root and `$HOME/.local` for regular users.
- Added explicit `--user`, `--system`, and `--prefix PATH` installer modes.
- Added mode-aware uninstall commands without removing source checkouts or high scores.
- Made installer output honest about PATH and direct-run commands.
- Ensured installed `sss` and `sss-snake` files are copied with executable mode `0755`.
- Changed the default autopilot to fast `--ai safe`, prioritizing smooth movement over perfect pathfinding.
- Added `--ai smart` and `--ai dumb` modes.
- Added `--path-refresh`, `--max-ai-cells`, and `--max-ai-steps` controls for bounded pathfinding.
- Reworked smart autopilot to cache paths and use one limited BFS from the snake head.
- Reduced default board size and fruit count for smoother server sessions.
- Updated README install, update, uninstall, and autopilot documentation.

## 0.3.0

- Added terminal-capped board sizing with a clear small-terminal error.
- Added automatic UTF-8 detection, `--ascii`, and safer Unicode rendering.
- Added wall edges by default, with optional `--wrap`.
- Added multiple fruit types, `--fruits`, and `--big-food` hitboxes.
- Replaced route-following autopilot with BFS fruit seeking plus tail/safe-move fallback.
- Added `away ate`, fruit count display, and new CLI documentation.

## 0.2.0

- Added safe first-run tmux bootstrap.
- Added tmux installation prompt with explicit confirmation.
- Added package manager detection for `apt`, `dnf`, `yum`, `pacman`, `zypper`, `apk`, and `brew`.
- Added fallback direct launch when tmux is missing or installation fails.
- Added `sss status`.
- Added `sss --version` and `sss-snake --version`.
- Added configurable board size.
- Added color themes and `NO_COLOR` support.
- Added persistent high score.
- Added public GitHub-oriented documentation.
- Added copy-paste GitHub install, update, and uninstall instructions.

## 0.1.0

- Initial Bash snake.
- Added autopilot mode.
- Added manual controls with arrows and `W A S D`.
- Added optional tmux support through `sss`.
