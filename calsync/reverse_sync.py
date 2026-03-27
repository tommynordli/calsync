# calsync/reverse_sync.py
import logging

import caldav

from calsync.diff import Event, compute_diff
from calsync.icloud_write import create_icloud_event, update_icloud_event, delete_icloud_event
from calsync.state import SyncState

logger = logging.getLogger(__name__)

TARGET_ID_KEY = "icloud_event_href"


def run_reverse_sync(
    events: list[Event],
    state: SyncState,
    calendar: caldav.Calendar,
    busy_only: bool = True,
    source_calendar_id: str = "",
    target_icloud_calendar: str = "",
):
    # Detect mode switch — force update all existing events
    force_update_all = False
    prev_busy_only = state.metadata.get("busy_only")
    if prev_busy_only is not None and prev_busy_only != busy_only:
        logger.info("Reverse sync busy_only changed from %s to %s — forcing update of all events",
                     prev_busy_only, busy_only)
        force_update_all = True

    to_create, to_update, to_delete = compute_diff(
        events, state.entries, target_id_key=TARGET_ID_KEY,
    )

    # If mode switched, add all unchanged events to the update list
    if force_update_all:
        already_updating = {e.uid for e, _ in to_update}
        creating = {e.uid for e in to_create}
        for event in events:
            if event.uid not in already_updating and event.uid not in creating and event.uid in state.entries:
                to_update.append((event, state.entries[event.uid][TARGET_ID_KEY]))

    logger.info("Reverse sync: %d create, %d update, %d delete",
                len(to_create), len(to_update), len(to_delete))

    for event in to_create:
        href = create_icloud_event(calendar, event, busy_only=busy_only)
        state.set_entry(event.uid, href, TARGET_ID_KEY,
                        event.start, event.end, event.all_day,
                        title=event.title, location=event.location,
                        description=event.description)
        state.save()

    for event, href in to_update:
        update_icloud_event(calendar, href, event, busy_only=busy_only)
        state.set_entry(event.uid, href, TARGET_ID_KEY,
                        event.start, event.end, event.all_day,
                        title=event.title, location=event.location,
                        description=event.description)
        state.save()

    for source_uid, href in to_delete:
        delete_icloud_event(calendar, href)
        state.remove(source_uid)
        state.save()

    # Save metadata
    state.set_metadata("busy_only", busy_only)
    if source_calendar_id:
        state.set_metadata("source_calendar_id", source_calendar_id)
    if target_icloud_calendar:
        state.set_metadata("target_icloud_calendar", target_icloud_calendar)
    state.save()


def purge_reverse_events(state: SyncState, calendar: caldav.Calendar):
    if not state.entries:
        print("No reverse-synced events to purge.")
        return

    count = len(state.entries)
    answer = input(f"Delete all {count} reverse-synced iCloud events and clear state? (y/n): ").strip().lower()
    if answer not in ("y", "yes"):
        print("Cancelled.")
        return

    for uid, entry in list(state.entries.items()):
        delete_icloud_event(calendar, entry[TARGET_ID_KEY])
        state.remove(uid)
        state.save()
        logger.info("Purged reverse-synced event %s", uid)

    state.clear()
    state.save()
    print(f"Purged {count} reverse-synced events and cleared state.")
