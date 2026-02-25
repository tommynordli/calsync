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
from calsync.update_check import check_remote, check_local

LOG_DIR = Path.home() / ".local" / "log"
LOG_FILE = LOG_DIR / "calsync.log"


def _setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    stream_handler.addFilter(logging.Filter("calsync"))

    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])


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
            logger.info("Using calendar '%s'", args.calendar)

        state = SyncState(args.state)

        # Handle calendar switch — delete from old calendar, not new one
        old_calendar_id = state.metadata.get("target_calendar_id")
        if old_calendar_id and old_calendar_id != calendar_id:
            old_gcal = GoogleCalClient(service=service, calendar_id=old_calendar_id)
            handle_calendar_switch(state, calendar_id, old_gcal, new_calendar_name=args.calendar or "")

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

        run_sync(events, state, gcal, busy_only=busy_only, calendar_id=calendar_id, calendar_name=args.calendar or "")
        logger.info("Sync complete")
        check_remote()
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
            logger.info("Using calendar '%s'", args.calendar)

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

    if sys.stdout.isatty():
        try:
            from calsync._commit import COMMIT
        except ImportError:
            COMMIT = "unknown"
        msg = check_local(COMMIT)
        if msg:
            print(msg)


if __name__ == "__main__":
    main()
