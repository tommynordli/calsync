# tests/test_sync.py
from unittest.mock import MagicMock
from calsync.sync import run_sync
from calsync.diff import Event
from calsync.state import SyncState


def test_sync_creates_new_events(tmp_path):
    state = SyncState(tmp_path / "state.json")
    gcal = MagicMock()
    gcal.create_event.return_value = "gid-new"

    events = [Event(uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T11:00:00+00:00", all_day=False)]

    run_sync(events, state, gcal, busy_only=True, calendar_id="work@gmail.com")

    gcal.create_event.assert_called_once()
    state_reloaded = SyncState(tmp_path / "state.json")
    assert "uid-1" in state_reloaded.entries


def test_sync_updates_changed_events(tmp_path):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00+00:00", "2026-03-01T11:00:00+00:00", False)
    state.save()

    gcal = MagicMock()
    events = [Event(uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T12:00:00+00:00", all_day=False)]

    run_sync(events, state, gcal, busy_only=True, calendar_id="work@gmail.com")

    gcal.update_event.assert_called_once()


def test_sync_deletes_removed_events(tmp_path):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00+00:00", "2026-03-01T11:00:00+00:00", False)
    state.save()

    gcal = MagicMock()
    events = []

    run_sync(events, state, gcal, busy_only=True, calendar_id="work@gmail.com")

    gcal.delete_event.assert_called_once_with("gid-1")
    state_reloaded = SyncState(tmp_path / "state.json")
    assert "uid-1" not in state_reloaded.entries


def test_sync_passes_busy_only_to_gcal(tmp_path):
    state = SyncState(tmp_path / "state.json")
    gcal = MagicMock()
    gcal.create_event.return_value = "gid-new"

    events = [Event(uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T11:00:00+00:00",
                    all_day=False, title="Meeting")]

    run_sync(events, state, gcal, busy_only=False, calendar_id="work@gmail.com")

    gcal.create_event.assert_called_once()
    _, kwargs = gcal.create_event.call_args
    assert kwargs["busy_only"] is False


def test_sync_mode_switch_forces_update(tmp_path):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00+00:00", "2026-03-01T11:00:00+00:00", False)
    state.set_metadata("busy_only", True)
    state.save()

    gcal = MagicMock()
    events = [Event(uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T11:00:00+00:00",
                    all_day=False, title="Meeting")]

    # Switch from busy_only=True to False — should force update all events
    run_sync(events, state, gcal, busy_only=False, calendar_id="work@gmail.com")

    gcal.update_event.assert_called_once()


def test_sync_saves_metadata(tmp_path):
    state = SyncState(tmp_path / "state.json")
    gcal = MagicMock()
    gcal.create_event.return_value = "gid-new"

    events = [Event(uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T11:00:00+00:00", all_day=False)]

    run_sync(events, state, gcal, busy_only=False, calendar_id="cal123")

    reloaded = SyncState(tmp_path / "state.json")
    assert reloaded.metadata["busy_only"] is False
    assert reloaded.metadata["target_calendar_id"] == "cal123"
