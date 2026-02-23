import shutil
import subprocess
import sys
from pathlib import Path

import caldav
import yaml

from cal_sync.google_cal import authenticate
from cal_sync.icloud import ICLOUD_CALDAV_URL

PLIST_TEMPLATE = "com.calsync.plist"
PLIST_DEST = Path.home() / "Library" / "LaunchAgents" / "com.calsync.plist"


def _prompt(message: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    result = input(f"{message}{suffix}: ").strip()
    return result or default


def _prompt_password(message: str) -> str:
    import getpass
    return getpass.getpass(f"{message}: ")


def _list_icloud_calendars(username: str, app_password: str) -> list[str]:
    client = caldav.DAVClient(
        url=ICLOUD_CALDAV_URL,
        username=username,
        password=app_password,
    )
    principal = client.principal()
    return [c.name for c in principal.calendars()]


def _pick_calendars(names: list[str]) -> list[str]:
    print("\nAvailable iCloud calendars:")
    for i, name in enumerate(names, 1):
        print(f"  {i}. {name}")
    print()
    picks = input("Which calendars to sync? (comma-separated numbers, e.g. 1,3): ").strip()
    indices = [int(x.strip()) - 1 for x in picks.split(",")]
    return [names[i] for i in indices if 0 <= i < len(names)]


def run_setup(project_dir: Path):
    print("=== calsync setup ===\n")

    # Step 1: iCloud credentials
    print("Step 1: iCloud credentials")
    print("  You need an app-specific password from https://appleid.apple.com")
    print("  (Sign-In and Security > App-Specific Passwords)\n")
    username = _prompt("iCloud email")
    app_password = _prompt_password("App-specific password")

    # Step 2: Connect and pick calendars
    print("\nConnecting to iCloud...")
    try:
        calendar_names = _list_icloud_calendars(username, app_password)
    except Exception as e:
        print(f"\nFailed to connect to iCloud: {e}")
        print("Check your username and app-specific password.")
        sys.exit(1)

    if not calendar_names:
        print("No calendars found on this iCloud account.")
        sys.exit(1)

    selected = _pick_calendars(calendar_names)
    if not selected:
        print("No calendars selected.")
        sys.exit(1)
    print(f"Selected: {', '.join(selected)}")

    # Step 3: Google Calendar
    print("\nStep 2: Google Calendar")
    calendar_id = _prompt("Google work calendar ID (usually your work email)")

    # Step 4: Google OAuth credentials
    credentials_file = project_dir / "credentials.json"
    if not credentials_file.exists():
        print(f"\nGoogle OAuth credentials file not found at: {credentials_file}")
        print("To get it:")
        print("  1. Go to https://console.cloud.google.com")
        print("  2. Create a project (or use existing)")
        print("  3. Enable the Google Calendar API")
        print("  4. Go to Credentials > Create Credentials > OAuth client ID > Desktop app")
        print(f"  5. Download the JSON and save it as: {credentials_file}")
        input("\nPress Enter when credentials.json is in place...")
        if not credentials_file.exists():
            print("credentials.json still not found. Exiting.")
            sys.exit(1)

    # Step 5: Write config
    config = {
        "icloud": {
            "username": username,
            "app_password": app_password,
            "calendars": selected,
        },
        "google": {
            "calendar_id": calendar_id,
            "credentials_file": "credentials.json",
            "token_file": "token.json",
        },
        "sync": {
            "lookahead_days": 30,
        },
    }
    config_path = project_dir / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    print(f"\nConfig written to {config_path}")

    # Step 6: Google OAuth
    print("\nStep 3: Google OAuth")
    print("A browser window will open for Google authorization...")
    try:
        authenticate(credentials_file, project_dir / "token.json")
        print("Google authentication complete.")
    except Exception as e:
        print(f"Google auth failed: {e}")
        sys.exit(1)

    # Step 7: Test sync
    print("\nStep 4: Test sync")
    answer = _prompt("Run a test sync now?", "y")
    if answer.lower() in ("y", "yes"):
        result = subprocess.run(
            [sys.executable, "-m", "cal_sync.cli", "--config", str(config_path)],
            cwd=project_dir,
        )
        if result.returncode != 0:
            print("Test sync failed. Check the output above.")
        else:
            print("Test sync succeeded!")

    # Step 8: Install launchd
    print("\nStep 5: Automatic scheduling")
    answer = _prompt("Install launchd plist to run every 15 minutes?", "y")
    if answer.lower() in ("y", "yes"):
        _install_launchd(project_dir)
    else:
        print("Skipped. You can install it later — see README.md.")

    print("\nSetup complete!")


def _install_launchd(project_dir: Path):
    template = project_dir / PLIST_TEMPLATE
    if not template.exists():
        print(f"Plist template not found at {template}")
        return

    venv_path = project_dir / ".venv"
    log_path = Path.home() / ".local" / "log"
    log_path.mkdir(parents=True, exist_ok=True)

    content = template.read_text()
    content = content.replace("VENV_PATH", str(venv_path))
    content = content.replace("PROJECT_PATH", str(project_dir))
    content = content.replace("LOG_PATH", str(log_path))

    PLIST_DEST.write_text(content)
    print(f"Plist installed to {PLIST_DEST}")

    subprocess.run(["launchctl", "load", str(PLIST_DEST)])
    print("Scheduler loaded. calsync will run every 15 minutes.")
