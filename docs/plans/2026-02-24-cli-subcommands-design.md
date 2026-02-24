# CLI Subcommands Refactor

## Summary

Convert the calsync CLI from flag-based actions (`--auth`, `--setup`, `--purge`) to proper subcommands (`calsync auth`, `calsync setup`, `calsync purge`, `calsync sync`). Flags like `--calendar`, `--busy-only`, `--config`, `--state` remain as flags on the relevant subcommands.

## Prerequisites

This change stacks on top of the `calsync-work` branch after the calendar selection & full event sync work is complete. All handler logic (sync, setup, auth, purge, calendar resolution, busy_only mode) already exists.

## CLI Surface

```
calsync <command> [flags]

Commands:
  sync     Sync iCloud events to Google Calendar
  setup    Interactive setup wizard
  auth     Run Google OAuth flow
  purge    Delete all synced events and clear state

Global flags (all commands):
  -h, --help      Show help
  --config PATH   Path to config file (default: ~/.config/calsync/config.yaml)
  --state PATH    Path to state file (default: ~/.config/calsync/state.json)

sync flags:
  --calendar NAME   Override target Google Calendar by name
  --busy-only       Sync as opaque busy blocks only

purge flags:
  --calendar NAME   Override target Google Calendar by name
```

Bare `calsync` with no subcommand shows help. `--help` works on every subcommand via argparse defaults.

## Approach

Use `argparse.add_subparsers()` — no new dependencies. Parent parser holds global flags, each subcommand gets its own subparser.

## Files Changed

1. **`calsync/cli.py`** — replace flat argparse with parent parser + subparsers. Each subcommand sets a `func` attribute that `main()` dispatches to. Handler functions (`_cmd_sync`, `_cmd_setup`, `_cmd_auth`, `_cmd_purge`) wrap the same logic that exists today.

2. **`calsync/setup.py`** (~line 134) — update test sync subprocess call from `calsync --config ...` to `calsync sync --config ...`.

3. **`calsync/com.calsync.plist`** — insert `sync` subcommand into ProgramArguments array.

4. **`CLAUDE.md`** — update usage examples.

## What Does NOT Change

- No logic changes in sync, setup, auth, or purge handlers
- No new dependencies
- No test changes (no CLI tests exist; handlers are tested at the module level)
- The `[project.scripts]` entry in `pyproject.toml` stays `calsync = "calsync.cli:main"`

## git-spice Stacking

Create a new branch stacked on `calsync-work` using `gs branch create`. Commit the CLI refactor there. The stack becomes: `main` → `calsync-work` (features) → new branch (CLI subcommands).
