# tests/test_sync.py
from unittest.mock import MagicMock
from calsync.sync import run_sync
from calsync.diff import Event
from calsync.state import SyncState


def test_sync_creates_new_events(tmp_path):
    state = SyncState(tmp_path / "state.json")
    gcal = MagicMock()
    gcal.create_busy_block.return_value = "gid-new"

    events = [Event(uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T11:00:00+00:00", all_day=False)]

    run_sync(events, state, gcal)

    gcal.create_busy_block.assert_called_once()
    state_reloaded = SyncState(tmp_path / "state.json")
    assert "uid-1" in state_reloaded.entries


def test_sync_updates_changed_events(tmp_path):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00+00:00", "2026-03-01T11:00:00+00:00", False)
    state.save()

    gcal = MagicMock()
    events = [Event(uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T12:00:00+00:00", all_day=False)]

    run_sync(events, state, gcal)

    gcal.update_busy_block.assert_called_once_with("gid-1", events[0])


def test_sync_deletes_removed_events(tmp_path):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00+00:00", "2026-03-01T11:00:00+00:00", False)
    state.save()

    gcal = MagicMock()
    events = []

    run_sync(events, state, gcal)

    gcal.delete_busy_block.assert_called_once_with("gid-1")
    state_reloaded = SyncState(tmp_path / "state.json")
    assert "uid-1" not in state_reloaded.entries
