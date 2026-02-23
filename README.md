# calsync

Syncs iCloud calendar events to a Google Calendar as "Busy" blocks. Runs every 15 minutes via macOS launchd, fetching events from one or more iCloud calendars and mirroring them as opaque busy entries on a target Google Calendar. Only changes (new, updated, deleted events) are pushed each cycle.

## Prerequisites

- Python 3.11+
- An iCloud account with an app-specific password
- A Google Cloud project with the Calendar API enabled and OAuth 2.0 credentials

## Quick Setup

```bash
git clone <repo-url> && cd calsync
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
calsync --setup
```

The setup wizard walks you through everything interactively: iCloud credentials, calendar selection, Google OAuth, a test sync, and launchd installation.

## Manual Setup

If you prefer to set things up manually:

1. Copy `config.yaml.example` to `config.yaml` and fill in your values.

2. Generate an iCloud app-specific password at <https://appleid.apple.com>.

3. Create a Google Cloud project, enable the **Google Calendar API**, create OAuth 2.0 credentials (desktop app), and save the downloaded JSON as `credentials.json`.

4. Run `calsync --auth` to complete the Google OAuth flow.

5. Test with `calsync`.

6. Install the launchd plist:

   ```bash
   cp com.calsync.plist ~/Library/LaunchAgents/
   sed -i '' "s|VENV_PATH|$(pwd)/.venv|g" ~/Library/LaunchAgents/com.calsync.plist
   sed -i '' "s|PROJECT_PATH|$(pwd)|g" ~/Library/LaunchAgents/com.calsync.plist
   sed -i '' "s|LOG_PATH|$HOME/.local/log|g" ~/Library/LaunchAgents/com.calsync.plist
   launchctl load ~/Library/LaunchAgents/com.calsync.plist
   ```

## Logs

Application logs are written to `~/.local/log/calsync.log`.

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.calsync.plist
rm ~/Library/LaunchAgents/com.calsync.plist
rm -rf .venv
```
