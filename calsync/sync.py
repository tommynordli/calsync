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
        state.set(event.uid, google_id, event.start, event.end, event.all_day)
        state.save()

    for event, google_id in to_update:
        gcal.update_event(google_id, event, busy_only=busy_only)
        state.set(event.uid, google_id, event.start, event.end, event.all_day)
        state.save()

    for icloud_uid, google_id in to_delete:
        gcal.delete_event(google_id)
        state.remove(icloud_uid)
        state.save()

    # Save metadata
    state.set_metadata("busy_only", busy_only)
    if calendar_id:
        state.set_metadata("target_calendar_id", calendar_id)
    state.save()
