from calsync.diff import Event, compute_diff


def test_new_event_creates():
    events = [Event(uid="uid-1", start="2026-03-01T10:00:00", end="2026-03-01T11:00:00", all_day=False)]
    state_entries = {}
    to_create, to_update, to_delete = compute_diff(events, state_entries)
    assert len(to_create) == 1
    assert to_create[0].uid == "uid-1"
    assert to_update == []
    assert to_delete == []


def test_unchanged_event_no_op():
    events = [Event(uid="uid-1", start="2026-03-01T10:00:00", end="2026-03-01T11:00:00", all_day=False)]
    state_entries = {
        "uid-1": {"google_event_id": "gid-1", "start": "2026-03-01T10:00:00", "end": "2026-03-01T11:00:00", "all_day": False},
    }
    to_create, to_update, to_delete = compute_diff(events, state_entries)
    assert to_create == []
    assert to_update == []
    assert to_delete == []


def test_time_change_updates():
    events = [Event(uid="uid-1", start="2026-03-01T10:00:00", end="2026-03-01T12:00:00", all_day=False)]
    state_entries = {
        "uid-1": {"google_event_id": "gid-1", "start": "2026-03-01T10:00:00", "end": "2026-03-01T11:00:00", "all_day": False},
    }
    to_create, to_update, to_delete = compute_diff(events, state_entries)
    assert to_create == []
    assert len(to_update) == 1
    assert to_update[0] == (events[0], "gid-1")
    assert to_delete == []


def test_removed_event_deletes():
    events = []
    state_entries = {
        "uid-1": {"google_event_id": "gid-1", "start": "2026-03-01T10:00:00", "end": "2026-03-01T11:00:00", "all_day": False},
    }
    to_create, to_update, to_delete = compute_diff(events, state_entries)
    assert to_create == []
    assert to_update == []
    assert to_delete == [("uid-1", "gid-1")]


def test_mixed_operations():
    events = [
        Event(uid="uid-1", start="2026-03-01T10:00:00", end="2026-03-01T11:00:00", all_day=False),  # unchanged
        Event(uid="uid-2", start="2026-03-02T14:00:00", end="2026-03-02T15:00:00", all_day=False),  # updated
        Event(uid="uid-4", start="2026-03-04T09:00:00", end="2026-03-04T10:00:00", all_day=False),  # new
    ]
    state_entries = {
        "uid-1": {"google_event_id": "gid-1", "start": "2026-03-01T10:00:00", "end": "2026-03-01T11:00:00", "all_day": False},
        "uid-2": {"google_event_id": "gid-2", "start": "2026-03-02T13:00:00", "end": "2026-03-02T14:00:00", "all_day": False},
        "uid-3": {"google_event_id": "gid-3", "start": "2026-03-03T10:00:00", "end": "2026-03-03T11:00:00", "all_day": False},
    }
    to_create, to_update, to_delete = compute_diff(events, state_entries)
    assert len(to_create) == 1
    assert to_create[0].uid == "uid-4"
    assert len(to_update) == 1
    assert to_update[0] == (events[1], "gid-2")
    assert len(to_delete) == 1
    assert to_delete[0] == ("uid-3", "gid-3")


def test_event_has_detail_fields():
    event = Event(
        uid="uid-1",
        start="2026-03-01T10:00:00",
        end="2026-03-01T11:00:00",
        all_day=False,
        title="Team standup",
        location="Room 3B",
        description="Daily sync",
    )
    assert event.title == "Team standup"
    assert event.location == "Room 3B"
    assert event.description == "Daily sync"


def test_event_detail_fields_default_empty():
    event = Event(uid="uid-1", start="2026-03-01T10:00:00", end="2026-03-01T11:00:00", all_day=False)
    assert event.title == ""
    assert event.location == ""
    assert event.description == ""
