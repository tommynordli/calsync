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

# CLI commands
calsync sync                          # Run a sync (both directions if reverse enabled)
calsync --config path/to/config.yaml sync
calsync sync --calendar "Work"        # Override target calendar
calsync sync --busy-only              # Sync as busy blocks only
calsync auth                          # Google OAuth flow only
calsync setup                         # Interactive setup wizard
calsync purge                         # Delete forward-synced events
calsync purge --reverse               # Delete reverse-synced iCloud events
calsync purge --all                   # Delete both directions
```

No linter, formatter, or pre-commit hooks are configured.

## Architecture

The sync engine supports **two-way sync** between iCloud and Google Calendar, running both directions in a single `calsync sync` invocation.

### Forward sync (iCloud → Google)

Follows a **source → diff → sink** pipeline:

1. `icloud.fetch_icloud_events()` — CalDAV date_search over a lookahead window → `list[Event]`
2. `diff.compute_diff(events, state)` → `(to_create, to_update, to_delete)` by comparing against persisted state
3. `sync.run_sync()` — applies creates/updates/deletes via `GoogleCalClient.create_event()`/`update_event()`/`delete_event()`, passing `busy_only` to control event body content. Detects mode switches and forces update of all events. `handle_calendar_switch()` detects calendar ID changes and optionally purges old events. `state.save()` after each mutation for crash safety.
4. `state.json` — envelope dict with `entries` mapping iCloud UIDs to `{google_event_id, start, end, all_day, title, location, description}`, plus `metadata` tracking `{target_calendar_id, busy_only}` for switch detection.

### Reverse sync (Google → iCloud)

Parallel pipeline that syncs native Google events to a dedicated iCloud calendar:

1. `google_cal.fetch_google_events()` — Google Calendar API list with pagination → `list[Event]`, skipping any event with `extendedProperties.private.icloud_uid` (loop prevention)
2. `diff.compute_diff(events, state, target_id_key="icloud_event_href")` — same diff engine, generic target ID key
3. `reverse_sync.run_reverse_sync()` — applies creates/updates/deletes via `icloud_write.create_icloud_event()`/`update_icloud_event()`/`delete_icloud_event()`
4. `reverse_state.json` — maps Google event IDs to `{icloud_event_href, start, end, all_day, ...}`

### Loop prevention (two layers)

| Direction | Primary | Safety net |
|-----------|---------|------------|
| iCloud → Google | Reverse sync writes to a dedicated iCloud calendar NOT in forward source list | `_parse_vevent` skips events with `X-CALSYNC-SOURCE:google` |
| Google → iCloud | `fetch_google_events` skips events with `extendedProperties.private.icloud_uid` | Reverse state tracks only native Google event IDs |

Synced Google events carry full details (title, location, description) by default. With `busy_only` mode, they become opaque "Busy" blocks. The iCloud UID is always stored in `extendedProperties.private.icloud_uid`. Reverse-synced iCloud events carry `X-CALSYNC-SOURCE:google` and use UID prefix `calsync-reverse-`.

## Key Conventions

- **Frozen dataclasses** for `Config` and `Event` (immutable after creation). `SyncState` is intentionally mutable.
- **Modern type hints**: `list[T]`, `dict[K, V]`, `X | None` (Python 3.10+).
- **Private helpers** use `_leading_underscore` (`_parse_vevent`, `_make_body`, `_prompt`).
- **Relative path resolution**: Config paths resolve relative to the config file's parent directory, not CWD. This is critical for `uv tool install` support.
- **Recurring events**: Each instance gets a unique UID by appending recurrence-id (`f"{uid}_{rid_str}"`), tracked separately in state.
- **Idempotent deletes**: `GoogleCalClient.delete_event()` catches HTTP 404 silently.
- **Busy-only mode**: `_make_body()` produces full-detail events by default (title, location, description from `Event`), opaque "Busy" blocks when `busy_only=True`.
- **Calendar helpers**: `list_owned_calendars(service)` and `resolve_calendar_by_name(name, calendars)` are standalone functions in `google_cal.py`.

## File Locations at Runtime

- Config/credentials: `~/.config/calsync/` (config.yaml, credentials.json, token.json, state.json, reverse_state.json)
- Logs: `~/.local/log/calsync.log`
- Launchd plist: `~/Library/LaunchAgents/com.calsync.plist`
- Plist template: bundled as package data in `calsync/com.calsync.plist`, loaded via `importlib.resources`

## Test Patterns

Tests use **pytest** with `tmp_path` for temp state files and `unittest.mock` for external services. iCloud tests mock `caldav.DAVClient` with custom `_make_mock_vevent()` builders. Google tests mock the API service object. No shared fixtures in conftest.py — each test file is self-contained.
