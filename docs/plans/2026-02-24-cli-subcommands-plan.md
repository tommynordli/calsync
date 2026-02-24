# CLI Subcommands Refactor — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert the calsync CLI from flag-based actions to proper subcommands (`calsync sync`, `calsync setup`, `calsync auth`, `calsync purge`).

**Architecture:** Replace the flat `argparse` parser with a parent parser + `add_subparsers()`. Global flags (`--config`, `--state`) live on the parent parser. Each subcommand gets its own subparser with command-specific flags. Handler functions wrap existing logic — no behavior changes.

**Tech Stack:** Python 3.10+, argparse (stdlib)

**Prerequisites:** This stacks on top of the `calsync-work` branch after the calendar selection & full event sync work is complete. The starting point is the CLI from Task 10 of the calendar-selection plan, which has `--auth`, `--setup`, `--calendar`, `--busy-only`, `--purge` flags.

---

### Task 1: Create the new branch stacked on calsync-work

**Step 1: Create stacked branch with git-spice**

Run:
```bash
gs branch create cli-subcommands
```

Expected: New branch `cli-subcommands` created, tracking `calsync-work` as its base.

---

### Task 2: Rewrite cli.py with subcommands

**Files:**
- Modify: `calsync/cli.py`

**Step 1: Replace the entire cli.py**

The post-miami `cli.py` uses a flat argparse with flags. Replace with subcommand-based dispatch:

```python
# calsync/cli.py
import argparse
import logging
import sys
from pathlib import Path

from calsync.config import load_config
from calsync.google_cal import (
    GoogleCalClient, authenticate, build_service,
    list_owned_calendars, resolve_calendar_by_name,
)
from calsync.icloud import fetch_icloud_events
from calsync.state import SyncState
from calsync.sync import run_sync, handle_calendar_switch, purge_events

LOG_DIR = Path.home() / ".local" / "log"
LOG_FILE = LOG_DIR / "calsync.log"


def _setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(),
        ],
    )


def _cmd_sync(args):
    _setup_logging()
    logger = logging.getLogger(__name__)

    config = load_config(args.config)

    logger.info("Starting sync...")
    try:
        creds = authenticate(config.google_credentials_file, config.google_token_file)
        service = build_service(creds)

        # Resolve calendar ID
        calendar_id = config.google_calendar_id
        if args.calendar:
            calendars = list_owned_calendars(service)
            calendar_id = resolve_calendar_by_name(args.calendar, calendars)
            logger.info("Resolved calendar '%s' to ID: %s", args.calendar, calendar_id)

        state = SyncState(args.state)

        # Handle calendar switch — delete from old calendar, not new one
        old_calendar_id = state.metadata.get("target_calendar_id")
        if old_calendar_id and old_calendar_id != calendar_id:
            old_gcal = GoogleCalClient(service=service, calendar_id=old_calendar_id)
            handle_calendar_switch(state, calendar_id, old_gcal)

        gcal = GoogleCalClient(service=service, calendar_id=calendar_id)

        # Determine busy_only — CLI flag overrides config
        busy_only = args.busy_only or config.busy_only

        events = fetch_icloud_events(
            username=config.icloud_username,
            app_password=config.icloud_app_password,
            calendar_names=config.icloud_calendars,
            lookahead_days=config.lookahead_days,
        )
        logger.info("Fetched %d events from iCloud", len(events))

        run_sync(events, state, gcal, busy_only=busy_only, calendar_id=calendar_id)
        logger.info("Sync complete")
    except Exception:
        logger.exception("Sync failed")
        sys.exit(1)


def _cmd_setup(args):
    from calsync.setup import run_setup
    run_setup()


def _cmd_auth(args):
    _setup_logging()
    logger = logging.getLogger(__name__)

    config = load_config(args.config)
    logger.info("Running Google OAuth authentication flow...")
    authenticate(config.google_credentials_file, config.google_token_file)
    logger.info("Authentication complete. Token saved to %s", config.google_token_file)


def _cmd_purge(args):
    _setup_logging()
    logger = logging.getLogger(__name__)

    config = load_config(args.config)

    try:
        creds = authenticate(config.google_credentials_file, config.google_token_file)
        service = build_service(creds)

        calendar_id = config.google_calendar_id
        if args.calendar:
            calendars = list_owned_calendars(service)
            calendar_id = resolve_calendar_by_name(args.calendar, calendars)
            logger.info("Resolved calendar '%s' to ID: %s", args.calendar, calendar_id)

        gcal = GoogleCalClient(service=service, calendar_id=calendar_id)
        state = SyncState(args.state)

        purge_events(state, gcal)
    except Exception:
        logger.exception("Purge failed")
        sys.exit(1)


def main():
    config_dir = Path.home() / ".config" / "calsync"

    parser = argparse.ArgumentParser(
        prog="calsync",
        description="Sync iCloud calendars to Google Calendar",
    )
    parser.add_argument("--config", type=Path, default=config_dir / "config.yaml",
                        help="Path to config file")
    parser.add_argument("--state", type=Path, default=config_dir / "state.json",
                        help="Path to state file")

    subparsers = parser.add_subparsers(dest="command")

    # sync
    sp_sync = subparsers.add_parser("sync", help="Sync iCloud events to Google Calendar")
    sp_sync.add_argument("--calendar", type=str,
                         help="Override target Google Calendar by name")
    sp_sync.add_argument("--busy-only", action="store_true",
                         help="Sync as opaque busy blocks only")
    sp_sync.set_defaults(func=_cmd_sync)

    # setup
    sp_setup = subparsers.add_parser("setup", help="Interactive setup wizard")
    sp_setup.set_defaults(func=_cmd_setup)

    # auth
    sp_auth = subparsers.add_parser("auth", help="Run Google OAuth flow")
    sp_auth.set_defaults(func=_cmd_auth)

    # purge
    sp_purge = subparsers.add_parser("purge", help="Delete all synced events and clear state")
    sp_purge.add_argument("--calendar", type=str,
                          help="Override target Google Calendar by name")
    sp_purge.set_defaults(func=_cmd_purge)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
```

**Step 2: Verify the help output**

Run: `python -m calsync.cli --help`

Expected output shows subcommands:
```
usage: calsync [-h] [--config CONFIG] [--state STATE] {sync,setup,auth,purge} ...

positional arguments:
  {sync,setup,auth,purge}
    sync                Sync iCloud events to Google Calendar
    setup               Interactive setup wizard
    auth                Run Google OAuth flow
    purge               Delete all synced events and clear state
```

Run: `python -m calsync.cli sync --help`

Expected output shows sync-specific flags:
```
usage: calsync sync [-h] [--calendar CALENDAR] [--busy-only]
```

**Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: ALL PASS (no CLI tests exist; module-level tests are unaffected)

**Step 4: Commit**

```bash
git add calsync/cli.py
git commit -m "refactor: convert CLI from flags to subcommands"
```

---

### Task 3: Update setup.py test sync command

**Files:**
- Modify: `calsync/setup.py` (the subprocess call ~line 132-134)

**Step 1: Update the test sync invocation**

Find this line in `run_setup()`:
```python
        result = subprocess.run(
            [sys.executable, "-m", "calsync.cli", "--config", str(config_path)],
        )
```

Replace with:
```python
        result = subprocess.run(
            [sys.executable, "-m", "calsync.cli", "sync", "--config", str(config_path)],
        )
```

**Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add calsync/setup.py
git commit -m "fix: update setup wizard test sync to use 'calsync sync' subcommand"
```

---

### Task 4: Update launchd plist template

**Files:**
- Modify: `calsync/com.calsync.plist`

**Step 1: Insert `sync` subcommand into ProgramArguments**

The current plist has:
```xml
    <key>ProgramArguments</key>
    <array>
        <string>VENV_PATH/bin/calsync</string>
        <string>--config</string>
        <string>PROJECT_PATH/config.yaml</string>
        <string>--state</string>
        <string>PROJECT_PATH/state.json</string>
    </array>
```

Replace with:
```xml
    <key>ProgramArguments</key>
    <array>
        <string>VENV_PATH/bin/calsync</string>
        <string>sync</string>
        <string>--config</string>
        <string>PROJECT_PATH/config.yaml</string>
        <string>--state</string>
        <string>PROJECT_PATH/state.json</string>
    </array>
```

**Step 2: Commit**

```bash
git add calsync/com.calsync.plist
git commit -m "fix: update launchd plist to use 'calsync sync' subcommand"
```

---

### Task 5: Update CLAUDE.md usage examples

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update the Commands section**

Replace the "Run sync manually" block:
```markdown
# Run sync manually
calsync
calsync --config path/to/config.yaml
calsync --auth      # Google OAuth flow only
calsync --setup     # Interactive setup wizard
calsync --calendar "Work"  # Override target Google Calendar by name
calsync --busy-only        # Sync as opaque busy blocks only
calsync --purge            # Delete all synced events and clear state
```

With:
```markdown
# CLI commands
calsync sync                          # Run a sync
calsync sync --config path/to/config.yaml
calsync sync --calendar "Work"        # Override target calendar
calsync sync --busy-only              # Sync as busy blocks only
calsync auth                          # Google OAuth flow only
calsync setup                         # Interactive setup wizard
calsync purge                         # Delete all synced events
```

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for subcommand-based CLI"
```

---

### Task 6: Final verification

**Step 1: Run the complete test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 2: Verify all subcommand help texts**

Run:
```bash
python -m calsync.cli --help
python -m calsync.cli sync --help
python -m calsync.cli setup --help
python -m calsync.cli auth --help
python -m calsync.cli purge --help
```

Expected: Each prints relevant help with `-h`/`--help` working.

**Step 3: Verify bare `calsync` shows help**

Run: `python -m calsync.cli`
Expected: Prints help text (same as `--help`), exits with code 0.
