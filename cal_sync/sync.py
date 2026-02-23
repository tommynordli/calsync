# cal_sync/sync.py
import logging

from cal_sync.diff import Event, compute_diff
from cal_sync.google_cal import GoogleCalClient
from cal_sync.state import SyncState

logger = logging.getLogger(__name__)


def run_sync(events: list[Event], state: SyncState, gcal: GoogleCalClient):
    to_create, to_update, to_delete = compute_diff(events, state.entries)

    logger.info("Sync: %d create, %d update, %d delete", len(to_create), len(to_update), len(to_delete))

    for event in to_create:
        google_id = gcal.create_busy_block(event)
        state.set(event.uid, google_id, event.start, event.end, event.all_day)

    for event, google_id in to_update:
        gcal.update_busy_block(google_id, event)
        state.set(event.uid, google_id, event.start, event.end, event.all_day)

    for icloud_uid, google_id in to_delete:
        gcal.delete_busy_block(google_id)
        state.remove(icloud_uid)

    state.save()
