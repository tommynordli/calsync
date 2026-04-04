# tests/test_sync.py
from unittest.mock import MagicMock
from calsync.sync import run_sync, handle_calendar_switch, purge_events
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

    run_sync(events, state, gcal, busy_only=False, calendar_id="cal123", calendar_name="Work")

    reloaded = SyncState(tmp_path / "state.json")
    assert reloaded.metadata["busy_only"] is False
    assert reloaded.metadata["target_calendar_id"] == "cal123"
    assert reloaded.metadata["target_calendar_name"] == "Work"


def test_handle_calendar_switch_deletes_old(tmp_path, monkeypatch):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00", "2026-03-01T11:00:00", False)
    state.set("uid-2", "gid-2", "2026-03-02T10:00:00", "2026-03-02T11:00:00", False)
    state.set_metadata("target_calendar_id", "old@gmail.com")
    state.set_metadata("target_calendar_name", "Old Calendar")
    state.save()

    old_gcal = MagicMock()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "y")

    switched = handle_calendar_switch(state, "new@gmail.com", old_gcal, new_calendar_name="New Calendar")

    assert switched is True
    assert old_gcal.delete_event.call_count == 2
    assert state.entries == {}


def test_handle_calendar_switch_keep_old(tmp_path, monkeypatch):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00", "2026-03-01T11:00:00", False)
    state.set_metadata("target_calendar_id", "old@gmail.com")
    state.set_metadata("target_calendar_name", "Old Calendar")
    state.save()

    old_gcal = MagicMock()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "n")

    switched = handle_calendar_switch(state, "new@gmail.com", old_gcal, new_calendar_name="New Calendar")

    assert switched is True
    old_gcal.delete_event.assert_not_called()
    assert state.entries == {}


def test_handle_calendar_switch_no_switch(tmp_path):
    state = SyncState(tmp_path / "state.json")
    state.set_metadata("target_calendar_id", "same@gmail.com")
    state.save()

    gcal = MagicMock()
    switched = handle_calendar_switch(state, "same@gmail.com", gcal)

    assert switched is False


def test_handle_calendar_switch_first_run(tmp_path):
    state = SyncState(tmp_path / "state.json")
    gcal = MagicMock()

    switched = handle_calendar_switch(state, "work@gmail.com", gcal)

    assert switched is False


def test_purge_events(tmp_path, monkeypatch):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00", "2026-03-01T11:00:00", False)
    state.set("uid-2", "gid-2", "2026-03-02T10:00:00", "2026-03-02T11:00:00", False)
    state.set_metadata("target_calendar_id", "work@gmail.com")
    state.save()

    gcal = MagicMock()
    monkeypatch.setattr("builtins.input", lambda _: "y")

    purge_events(state, gcal)

    assert gcal.delete_event.call_count == 2
    reloaded = SyncState(tmp_path / "state.json")
    assert reloaded.entries == {}
    assert reloaded.metadata == {}


def test_purge_events_cancel(tmp_path, monkeypatch):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00", "2026-03-01T11:00:00", False)
    state.save()

    gcal = MagicMock()
    monkeypatch.setattr("builtins.input", lambda _: "n")

    purge_events(state, gcal)

    gcal.delete_event.assert_not_called()
