# tests/test_reverse_sync.py
from unittest.mock import MagicMock, patch
from calsync.reverse_sync import run_reverse_sync, purge_reverse_events
from calsync.diff import Event
from calsync.state import SyncState


def test_reverse_sync_creates_new_events(tmp_path):
    state = SyncState(tmp_path / "reverse_state.json")
    calendar = MagicMock()

    with patch("calsync.reverse_sync.create_icloud_event") as mock_create:
        mock_create.return_value = "https://caldav.icloud.com/123/event.ics"

        events = [Event(uid="gid-1", start="2026-03-01T10:00:00+00:00",
                        end="2026-03-01T11:00:00+00:00", all_day=False, title="Meeting")]

        run_reverse_sync(events, state, calendar, busy_only=True,
                         source_calendar_id="work@gmail.com",
                         target_icloud_calendar="Work Events")

        mock_create.assert_called_once()
        reloaded = SyncState(tmp_path / "reverse_state.json")
        assert "gid-1" in reloaded.entries
        assert reloaded.entries["gid-1"]["icloud_event_href"] == "https://caldav.icloud.com/123/event.ics"


def test_reverse_sync_updates_changed_events(tmp_path):
    state = SyncState(tmp_path / "reverse_state.json")
    state.set_entry("gid-1", "https://caldav.icloud.com/123/event.ics", "icloud_event_href",
                    "2026-03-01T10:00:00+00:00", "2026-03-01T11:00:00+00:00", False)
    state.save()

    calendar = MagicMock()

    with patch("calsync.reverse_sync.update_icloud_event") as mock_update:
        events = [Event(uid="gid-1", start="2026-03-01T10:00:00+00:00",
                        end="2026-03-01T12:00:00+00:00", all_day=False)]

        run_reverse_sync(events, state, calendar, busy_only=True,
                         source_calendar_id="work@gmail.com",
                         target_icloud_calendar="Work Events")

        mock_update.assert_called_once()


def test_reverse_sync_deletes_removed_events(tmp_path):
    state = SyncState(tmp_path / "reverse_state.json")
    state.set_entry("gid-1", "https://caldav.icloud.com/123/event.ics", "icloud_event_href",
                    "2026-03-01T10:00:00+00:00", "2026-03-01T11:00:00+00:00", False)
    state.save()

    calendar = MagicMock()

    with patch("calsync.reverse_sync.delete_icloud_event") as mock_delete:
        events = []  # Event removed from Google

        run_reverse_sync(events, state, calendar, busy_only=True,
                         source_calendar_id="work@gmail.com",
                         target_icloud_calendar="Work Events")

        mock_delete.assert_called_once_with(calendar, "https://caldav.icloud.com/123/event.ics")
        reloaded = SyncState(tmp_path / "reverse_state.json")
        assert "gid-1" not in reloaded.entries


def test_reverse_sync_passes_busy_only(tmp_path):
    state = SyncState(tmp_path / "reverse_state.json")
    calendar = MagicMock()

    with patch("calsync.reverse_sync.create_icloud_event") as mock_create:
        mock_create.return_value = "https://caldav.icloud.com/123/event.ics"

        events = [Event(uid="gid-1", start="2026-03-01T10:00:00+00:00",
                        end="2026-03-01T11:00:00+00:00", all_day=False)]

        run_reverse_sync(events, state, calendar, busy_only=False,
                         source_calendar_id="work@gmail.com",
                         target_icloud_calendar="Work Events")

        _, kwargs = mock_create.call_args
        assert kwargs["busy_only"] is False


def test_reverse_sync_mode_switch_forces_update(tmp_path):
    state = SyncState(tmp_path / "reverse_state.json")
    state.set_entry("gid-1", "https://caldav.icloud.com/123/event.ics", "icloud_event_href",
                    "2026-03-01T10:00:00+00:00", "2026-03-01T11:00:00+00:00", False)
    state.set_metadata("busy_only", True)
    state.save()

    calendar = MagicMock()

    with patch("calsync.reverse_sync.update_icloud_event") as mock_update:
        events = [Event(uid="gid-1", start="2026-03-01T10:00:00+00:00",
                        end="2026-03-01T11:00:00+00:00", all_day=False)]

        # Switch from busy_only=True to False
        run_reverse_sync(events, state, calendar, busy_only=False,
                         source_calendar_id="work@gmail.com",
                         target_icloud_calendar="Work Events")

        mock_update.assert_called_once()


def test_reverse_sync_saves_metadata(tmp_path):
    state = SyncState(tmp_path / "reverse_state.json")
    calendar = MagicMock()

    with patch("calsync.reverse_sync.create_icloud_event") as mock_create:
        mock_create.return_value = "https://caldav.icloud.com/123/event.ics"

        events = [Event(uid="gid-1", start="2026-03-01T10:00:00+00:00",
                        end="2026-03-01T11:00:00+00:00", all_day=False)]

        run_reverse_sync(events, state, calendar, busy_only=True,
                         source_calendar_id="work@gmail.com",
                         target_icloud_calendar="Work Events")

        reloaded = SyncState(tmp_path / "reverse_state.json")
        assert reloaded.metadata["busy_only"] is True
        assert reloaded.metadata["source_calendar_id"] == "work@gmail.com"
        assert reloaded.metadata["target_icloud_calendar"] == "Work Events"


def test_purge_reverse_events(tmp_path, monkeypatch):
    state = SyncState(tmp_path / "reverse_state.json")
    state.set_entry("gid-1", "https://caldav.icloud.com/1/event.ics", "icloud_event_href",
                    "2026-03-01T10:00:00", "2026-03-01T11:00:00", False)
    state.set_entry("gid-2", "https://caldav.icloud.com/2/event.ics", "icloud_event_href",
                    "2026-03-02T10:00:00", "2026-03-02T11:00:00", False)
    state.save()

    calendar = MagicMock()
    monkeypatch.setattr("builtins.input", lambda _: "y")

    with patch("calsync.reverse_sync.delete_icloud_event") as mock_delete:
        purge_reverse_events(state, calendar)

        assert mock_delete.call_count == 2
        reloaded = SyncState(tmp_path / "reverse_state.json")
        assert reloaded.entries == {}


def test_purge_reverse_events_cancel(tmp_path, monkeypatch):
    state = SyncState(tmp_path / "reverse_state.json")
    state.set_entry("gid-1", "https://caldav.icloud.com/1/event.ics", "icloud_event_href",
                    "2026-03-01T10:00:00", "2026-03-01T11:00:00", False)
    state.save()

    calendar = MagicMock()
    monkeypatch.setattr("builtins.input", lambda _: "n")

    with patch("calsync.reverse_sync.delete_icloud_event") as mock_delete:
        purge_reverse_events(state, calendar)

        mock_delete.assert_not_called()
