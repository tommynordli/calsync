# tests/test_state.py
import json
from calsync.state import SyncState


def test_load_empty(tmp_path):
    state_file = tmp_path / "state.json"
    state = SyncState(state_file)
    assert state.entries == {}


def test_load_existing(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({
        "uid-1": {"google_event_id": "gid-1", "start": "2026-03-01T10:00:00", "end": "2026-03-01T11:00:00", "all_day": False},
    }))
    state = SyncState(state_file)
    assert "uid-1" in state.entries
    assert state.entries["uid-1"]["google_event_id"] == "gid-1"


def test_set_and_save(tmp_path):
    state_file = tmp_path / "state.json"
    state = SyncState(state_file)
    state.set("uid-2", "gid-2", "2026-03-02T09:00:00", "2026-03-02T10:00:00", False)
    state.save()

    reloaded = SyncState(state_file)
    assert reloaded.entries["uid-2"]["google_event_id"] == "gid-2"


def test_remove_and_save(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({
        "uid-1": {"google_event_id": "gid-1", "start": "2026-03-01T10:00:00", "end": "2026-03-01T11:00:00", "all_day": False},
    }))
    state = SyncState(state_file)
    state.remove("uid-1")
    state.save()

    reloaded = SyncState(state_file)
    assert "uid-1" not in reloaded.entries


def test_metadata_default_empty(tmp_path):
    state = SyncState(tmp_path / "state.json")
    assert state.metadata == {}


def test_set_metadata_and_save(tmp_path):
    state_file = tmp_path / "state.json"
    state = SyncState(state_file)
    state.set_metadata("target_calendar_id", "work@gmail.com")
    state.set_metadata("busy_only", True)
    state.save()

    reloaded = SyncState(state_file)
    assert reloaded.metadata["target_calendar_id"] == "work@gmail.com"
    assert reloaded.metadata["busy_only"] is True


def test_metadata_preserved_with_entries(tmp_path):
    state_file = tmp_path / "state.json"
    state = SyncState(state_file)
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00", "2026-03-01T11:00:00", False)
    state.set_metadata("target_calendar_id", "work@gmail.com")
    state.save()

    reloaded = SyncState(state_file)
    assert "uid-1" in reloaded.entries
    assert reloaded.metadata["target_calendar_id"] == "work@gmail.com"


def test_clear_entries_preserves_nothing(tmp_path):
    state_file = tmp_path / "state.json"
    state = SyncState(state_file)
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00", "2026-03-01T11:00:00", False)
    state.set_metadata("target_calendar_id", "work@gmail.com")
    state.save()

    state.clear()
    state.save()

    reloaded = SyncState(state_file)
    assert reloaded.entries == {}
    assert reloaded.metadata == {}
