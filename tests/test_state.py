# tests/test_state.py
import json
from cal_sync.state import SyncState


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
