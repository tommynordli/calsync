# calsync/sync.py
import logging

from calsync.diff import Event, compute_diff
from calsync.google_cal import GoogleCalClient
from calsync.state import SyncState

logger = logging.getLogger(__name__)


def run_sync(
    events: list[Event],
    state: SyncState,
    gcal: GoogleCalClient,
    busy_only: bool = True,
    calendar_id: str = "",
    calendar_name: str = "",
):
    # Detect mode switch — force update all existing events
    force_update_all = False
    prev_busy_only = state.metadata.get("busy_only")
    if prev_busy_only is not None and prev_busy_only != busy_only:
        logger.info("busy_only changed from %s to %s — forcing update of all events", prev_busy_only, busy_only)
        force_update_all = True

    to_create, to_update, to_delete = compute_diff(events, state.entries)

    # If mode switched, add all unchanged events to the update list
    if force_update_all:
        already_updating = {e.uid for e, _ in to_update}
        creating = {e.uid for e in to_create}
        for event in events:
            if event.uid not in already_updating and event.uid not in creating and event.uid in state.entries:
                to_update.append((event, state.entries[event.uid]["google_event_id"]))

    logger.info("Sync: %d create, %d update, %d delete", len(to_create), len(to_update), len(to_delete))

    for event in to_create:
        google_id = gcal.create_event(event, busy_only=busy_only)
        state.set(event.uid, google_id, event.start, event.end, event.all_day,
                  title=event.title, location=event.location, description=event.description)
        state.save()

    for event, google_id in to_update:
        gcal.update_event(google_id, event, busy_only=busy_only)
        state.set(event.uid, google_id, event.start, event.end, event.all_day,
                  title=event.title, location=event.location, description=event.description)
        state.save()

    for icloud_uid, google_id in to_delete:
        gcal.delete_event(google_id)
        state.remove(icloud_uid)
        state.save()

    # Save metadata
    state.set_metadata("busy_only", busy_only)
    if calendar_id:
        state.set_metadata("target_calendar_id", calendar_id)
    if calendar_name:
        state.set_metadata("target_calendar_name", calendar_name)
    state.save()


def handle_calendar_switch(
    state: SyncState, new_calendar_id: str, gcal: GoogleCalClient,
    new_calendar_name: str = "",
) -> bool:
    old_calendar_id = state.metadata.get("target_calendar_id")
    if not old_calendar_id or old_calendar_id == new_calendar_id:
        return False

    old_name = state.metadata.get("target_calendar_name", old_calendar_id)
    new_name = new_calendar_name or new_calendar_id
    logger.info("Switching calendar: '%s' → '%s'", old_name, new_name)
    answer = input(
        f"Events are currently synced to '{old_name}'. "
        f"Delete them before syncing to '{new_name}'? (y/n): "
    ).strip().lower()

    if answer in ("y", "yes"):
        for uid, entry in list(state.entries.items()):
            gcal.delete_event(entry["google_event_id"])
            logger.info("Deleted %s from old calendar", uid)

    state.clear()
    state.save()
    return True


def purge_events(state: SyncState, gcal: GoogleCalClient):
    if not state.entries:
        print("No synced events to purge.")
        return

    count = len(state.entries)
    answer = input(f"Delete all {count} synced events and clear state? (y/n): ").strip().lower()
    if answer not in ("y", "yes"):
        print("Cancelled.")
        return

    for uid, entry in list(state.entries.items()):
        gcal.delete_event(entry["google_event_id"])
        state.remove(uid)
        state.save()
        logger.info("Purged %s", uid)

    state.clear()
    state.save()
    print(f"Purged {count} events and cleared state.")
