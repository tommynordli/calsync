# Google Calendar Selection & Full Event Sync

## Summary

Two related changes: (1) let users choose which Google Calendar to sync to, and (2) sync full event details by default instead of opaque "Busy" blocks.

## Config Changes

```yaml
google:
  calendar_id: "abc123@group.calendar.google.com"  # resolved from name during setup
  credentials_file: "credentials.json"
  token_file: "token.json"

sync:
  lookahead_days: 30
  busy_only: false  # default false — sync title, time, location, description
```

- `busy_only` defaults to `false` (full details)
- `Config` dataclass gets a new `busy_only: bool` field
- `Event` dataclass gets `title`, `location`, `description` fields

## Setup Wizard Changes

New step after Google OAuth:

1. Call `calendarList.list()` with `minAccessRole=owner` to list owned calendars
2. Display as numbered list, user picks by number
3. If two calendars share a name, show both with their IDs and ask user to pick
4. Ask "Sync full event details or busy blocks only?" (default: full details)
5. Store calendar ID and `busy_only` in config

Replaces the existing text prompt for calendar ID.

## CLI Flags

- `calsync --calendar "Work"` — resolve name to ID at startup (list owned calendars, match by name, disambiguate duplicates). Overrides `google.calendar_id` for that run.
- `calsync --busy-only` — override `sync.busy_only` to `true` for that run.
- `calsync --purge` — delete all tracked events from current target calendar, clear state. Prompts for confirmation.

## Event Body

**Full details mode** (`busy_only: false`):
- `summary` = event title
- `location` = event location (if present)
- `description` = event description (if present)
- `start`/`end`, `extendedProperties`, `transparency` = same as today

**Busy-only mode** (`busy_only: true`):
- Same as current behavior — summary is "Busy", no location/description

`_parse_vevent()` extracts title, location, description from iCloud vevents. `_make_body()` takes `busy_only` param to decide what to include.

## Calendar & Mode Switching

**State tracking**: `state.json` gets `target_calendar_id` and `busy_only` metadata fields.

**Calendar switch**:
1. Detect mismatch between config/flag calendar ID and state's `target_calendar_id`
2. Prompt: "Events are currently synced to [old]. Delete them before syncing to [new]? (y/n)"
3. If yes: delete all tracked events from old calendar, clear state, sync fresh
4. If no: clear state, sync fresh (orphans remain on old calendar)

**Mode switch**: When `busy_only` value changes from last sync, diff engine treats all existing events as needing update. Next sync rewrites every event body.

Both detections happen at the start of `run_sync()` before the normal diff pipeline.

## Purge Command

`calsync --purge`:
1. Confirm with user
2. Walk state file, call `delete_busy_block()` for each entry
3. Clear state

## Testing

- Google calendar listing: mock `calendarList.list()`, verify only owned calendars shown
- Name resolution: match, duplicate disambiguation, no-match error
- Event body: `_make_body()` in both modes
- Mode switch detection: changing `busy_only` triggers full update
- Calendar switch detection: prompt and delete flow
- Purge: all state entries deleted, state cleared
- CLI flags: `--calendar` and `--busy-only` override config values

All tests follow existing patterns: pytest, `tmp_path`, `unittest.mock`, self-contained files.
