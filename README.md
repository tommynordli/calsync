# cal-sync

Syncs iCloud calendar events to a Google Calendar as "Busy" blocks. Runs every 15 minutes via macOS launchd, fetching events from one or more iCloud calendars and mirroring them as opaque busy entries on a target Google Calendar. Only changes (new, updated, deleted events) are pushed each cycle.

## Prerequisites

- Python 3.11+
- An iCloud account with an app-specific password
- A Google Cloud project with the Calendar API enabled and OAuth 2.0 credentials

## Setup

1. Clone the repo and create a virtual environment:

   ```bash
   git clone <repo-url> && cd cal-sync
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install the package:

   ```bash
   pip install -e ".[dev]"
   ```

3. Copy the example config and fill in your values:

   ```bash
   cp config.yaml.example config.yaml
   ```

   Edit `config.yaml` with your iCloud username, calendar names, Google calendar ID, and credential file paths.

4. Generate an iCloud app-specific password at <https://appleid.apple.com>. Paste it into `config.yaml` under `icloud.app_password`.

5. Create a Google Cloud project, enable the **Google Calendar API**, create OAuth 2.0 credentials (desktop app), and download the credentials JSON file. Save it as `credentials.json` in the project directory (or wherever `config.yaml` points).

6. Run the OAuth flow to authorize Google Calendar access:

   ```bash
   cal-sync --auth
   ```

   This opens a browser window. Sign in and grant access. A `token.json` file is saved locally.

7. Test with a manual sync run:

   ```bash
   cal-sync
   ```

   Check the output and `~/.local/log/cal-sync.log` to confirm events were synced.

8. Install the launchd plist for automatic scheduling:

   ```bash
   cp com.cal-sync.plist ~/Library/LaunchAgents/

   # Replace placeholders with your actual paths
   sed -i '' "s|VENV_PATH|$HOME/path-to/cal-sync/.venv|g" ~/Library/LaunchAgents/com.cal-sync.plist
   sed -i '' "s|PROJECT_PATH|$HOME/path-to/cal-sync|g" ~/Library/LaunchAgents/com.cal-sync.plist
   sed -i '' "s|LOG_PATH|$HOME/.local/log|g" ~/Library/LaunchAgents/com.cal-sync.plist

   launchctl load ~/Library/LaunchAgents/com.cal-sync.plist
   ```

## Logs

Application logs are written to `~/.local/log/cal-sync.log`. The launchd plist also captures stdout and stderr separately in the configured `LOG_PATH` directory.

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.cal-sync.plist
rm ~/Library/LaunchAgents/com.cal-sync.plist
rm -rf /path/to/cal-sync/.venv
```
