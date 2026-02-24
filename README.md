# calsync

Syncs iCloud calendar events to a Google Calendar as "Busy" blocks. Runs every 15 minutes via macOS launchd, fetching events from one or more iCloud calendars and mirroring them as opaque busy entries on a target Google Calendar. Only changes (new, updated, deleted events) are pushed each cycle.

## Prerequisites

- Python 3.11+
- An iCloud account with an app-specific password
- A Google Cloud project with the Calendar API enabled and OAuth 2.0 credentials

## Install

```bash
uv tool install "calsync @ git+https://github.com/tommynordli/calsync"
calsync setup
```

The setup wizard walks you through everything interactively: iCloud credentials, calendar selection, Google OAuth, a test sync, and launchd installation. All config is stored in `~/.config/calsync/`.

## Development Setup

```bash
git clone https://github.com/tommynordli/calsync && cd calsync
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
calsync setup
```

## Manual Setup

If you prefer to set things up manually:

1. Create `~/.config/calsync/config.yaml` (see `config.yaml.example` for the format).

2. Generate an iCloud app-specific password at <https://appleid.apple.com>.

3. Create a Google Cloud project, enable the **Google Calendar API**, create OAuth 2.0 credentials (desktop app), and save the downloaded JSON as `~/.config/calsync/credentials.json`.

4. Run `calsync auth` to complete the Google OAuth flow.

5. Test with `calsync sync`.

## Logs

Application logs are written to `~/.local/log/calsync.log`.

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.calsync.plist
rm ~/Library/LaunchAgents/com.calsync.plist
uv tool uninstall calsync
rm -rf ~/.config/calsync
```
