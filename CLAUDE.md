# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_diff.py -v

# Run a specific test
pytest tests/test_diff.py::test_mixed_operations -v

# Run sync manually
calsync
calsync --config path/to/config.yaml
calsync --auth      # Google OAuth flow only
calsync --setup     # Interactive setup wizard
```

No linter, formatter, or pre-commit hooks are configured.

## Architecture

The sync engine follows a **source → diff → sink** pipeline:

1. `icloud.fetch_icloud_events()` — CalDAV date_search over a lookahead window → `list[Event]`
2. `diff.compute_diff(events, state)` → `(to_create, to_update, to_delete)` by comparing against persisted state
3. `sync.run_sync()` — applies creates/updates/deletes via `GoogleCalClient`, calling `state.save()` after each mutation for crash safety
4. `state.json` — flat dict mapping iCloud UIDs to `{google_event_id, start, end, all_day}`

All synced Google events are opaque "Busy" blocks with the iCloud UID stored in `extendedProperties.private.icloud_uid`.

## Key Conventions

- **Frozen dataclasses** for `Config` and `Event` (immutable after creation). `SyncState` is intentionally mutable.
- **Modern type hints**: `list[T]`, `dict[K, V]`, `X | None` (Python 3.10+).
- **Private helpers** use `_leading_underscore` (`_parse_vevent`, `_make_body`, `_prompt`).
- **Relative path resolution**: Config paths resolve relative to the config file's parent directory, not CWD. This is critical for `uv tool install` support.
- **Recurring events**: Each instance gets a unique UID by appending recurrence-id (`f"{uid}_{rid_str}"`), tracked separately in state.
- **Idempotent deletes**: `GoogleCalClient.delete_busy_block()` catches HTTP 404 silently.

## File Locations at Runtime

- Config/credentials: `~/.config/calsync/` (config.yaml, credentials.json, token.json)
- Logs: `~/.local/log/calsync.log`
- Launchd plist: `~/Library/LaunchAgents/com.calsync.plist`
- Plist template: bundled as package data in `calsync/com.calsync.plist`, loaded via `importlib.resources`

## Test Patterns

Tests use **pytest** with `tmp_path` for temp state files and `unittest.mock` for external services. iCloud tests mock `caldav.DAVClient` with custom `_make_mock_vevent()` builders. Google tests mock the API service object. No shared fixtures in conftest.py — each test file is self-contained.
