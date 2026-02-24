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


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(),
        ],
    )


def main():
    parser = argparse.ArgumentParser(description="Sync iCloud calendars to Google Calendar")
    config_dir = Path.home() / ".config" / "calsync"
    parser.add_argument("--config", type=Path, default=config_dir / "config.yaml", help="Path to config file")
    parser.add_argument("--state", type=Path, default=config_dir / "state.json", help="Path to state file")
    parser.add_argument("--auth", action="store_true", help="Run OAuth flow and exit")
    parser.add_argument("--setup", action="store_true", help="Interactive setup wizard")
    parser.add_argument("--calendar", type=str, help="Override target Google Calendar by name")
    parser.add_argument("--busy-only", action="store_true", help="Sync as opaque busy blocks only")
    parser.add_argument("--purge", action="store_true", help="Delete all synced events and clear state")
    args = parser.parse_args()

    if args.setup:
        from calsync.setup import run_setup
        run_setup()
        return

    setup_logging()
    logger = logging.getLogger(__name__)

    config = load_config(args.config)

    if args.auth:
        logger.info("Running Google OAuth authentication flow...")
        authenticate(config.google_credentials_file, config.google_token_file)
        logger.info("Authentication complete. Token saved to %s", config.google_token_file)
        return

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

        gcal = GoogleCalClient(service=service, calendar_id=calendar_id)
        state = SyncState(args.state)

        # Handle purge
        if args.purge:
            purge_events(state, gcal)
            return

        # Handle calendar switch
        handle_calendar_switch(state, calendar_id, gcal)

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


if __name__ == "__main__":
    main()
