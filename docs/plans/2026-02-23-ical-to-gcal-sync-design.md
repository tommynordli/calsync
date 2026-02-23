# iCloud to Google Calendar Sync — Design

## Problem

Sync two personal iCloud calendars to a Google work calendar as "Busy" blocks, without paying for a service like onecal.io.

## Decisions

- **Runtime:** Python script on macOS, scheduled via launchd every 15 minutes
- **iCloud access:** CalDAV with app-specific password
- **Google access:** Google Calendar API with OAuth2 (stored refresh token)
- **Sync behavior:** Full create/update/delete of busy blocks

## Architecture

A single `sync.py` script:

1. Fetch events from both iCloud calendars via CalDAV
2. Load previous state from `state.json`
3. Diff: determine which busy blocks to create, update, or delete on Google
4. Push changes to Google Calendar API
5. Save new state to `state.json`

## Event Mapping

Each iCloud event becomes a Google Calendar event with:

- **Title:** "Busy"
- **Start/end:** copied from original
- **Status:** opaque (shows as busy)
- **Description:** empty
- **Extended property:** stores original iCloud event UID for tracking

## State Tracking

`state.json` maps iCloud UIDs to Google event IDs:

```json
{
  "icloud-uid-abc123": "google-event-id-xyz"
}
```

Diff logic:

- iCloud event not in state → create busy block on Google
- iCloud event in state but time changed → update Google event
- State entry with no matching iCloud event → delete from Google
- All-day events → synced as all-day busy blocks

## Configuration

`config.yaml`:

```yaml
icloud:
  username: "your@icloud.com"
  app_password: "xxxx-xxxx-xxxx-xxxx"
  calendars:
    - "Personal"
    - "Family"

google:
  calendar_id: "your.work@gmail.com"
  credentials_file: "credentials.json"
  token_file: "token.json"

sync:
  lookahead_days: 30
```

## Setup Steps

1. Generate iCloud app-specific password at appleid.apple.com
2. Create Google Cloud project, enable Calendar API, download OAuth credentials
3. Run `python sync.py --auth` to complete browser consent flow
4. Install launchd plist for 15-minute schedule

## Dependencies

- `caldav`
- `google-api-python-client`
- `google-auth-oauthlib`
- `pyyaml`

## Error Handling

- Network failures: log and exit, next run retries
- Expired Google token: auto-refresh, log if refresh fails
- iCloud auth failure: log and exit
- Duplicate prevention: UID mapping in state.json
- Recurring events: expand into individual occurrences within lookahead window
- Cancelled/declined events: skip

## Logging

File log at `~/.local/log/calsync.log`.
