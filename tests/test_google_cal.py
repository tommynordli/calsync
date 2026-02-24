from unittest.mock import MagicMock, patch
from pathlib import Path
from calsync.google_cal import GoogleCalClient, list_owned_calendars
from calsync.diff import Event
from googleapiclient.errors import HttpError
import httplib2


def _mock_service():
    service = MagicMock()
    events_resource = MagicMock()
    service.events.return_value = events_resource
    return service, events_resource


def test_create_busy_block():
    service, events_resource = _mock_service()
    events_resource.insert.return_value.execute.return_value = {"id": "gid-new"}

    client = GoogleCalClient(service=service, calendar_id="work@gmail.com")
    event = Event(uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T11:00:00+00:00", all_day=False)
    google_id = client.create_busy_block(event)

    assert google_id == "gid-new"
    call_args = events_resource.insert.call_args
    body = call_args[1]["body"] if "body" in call_args[1] else call_args[0][0]
    assert body["summary"] == "Busy"
    assert body["transparency"] == "opaque"


def test_create_all_day_busy_block():
    service, events_resource = _mock_service()
    events_resource.insert.return_value.execute.return_value = {"id": "gid-new"}

    client = GoogleCalClient(service=service, calendar_id="work@gmail.com")
    event = Event(uid="uid-1", start="2026-03-01", end="2026-03-02", all_day=True)
    client.create_busy_block(event)

    call_args = events_resource.insert.call_args
    body = call_args[1]["body"]
    assert "date" in body["start"]
    assert "dateTime" not in body["start"]


def test_update_busy_block():
    service, events_resource = _mock_service()
    events_resource.update.return_value.execute.return_value = {"id": "gid-1"}

    client = GoogleCalClient(service=service, calendar_id="work@gmail.com")
    event = Event(uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T12:00:00+00:00", all_day=False)
    client.update_busy_block("gid-1", event)

    events_resource.update.assert_called_once()


def test_delete_busy_block():
    service, events_resource = _mock_service()
    events_resource.delete.return_value.execute.return_value = None

    client = GoogleCalClient(service=service, calendar_id="work@gmail.com")
    client.delete_busy_block("gid-1")

    events_resource.delete.assert_called_once_with(calendarId="work@gmail.com", eventId="gid-1")


def test_delete_already_gone():
    service, events_resource = _mock_service()
    resp = httplib2.Response({"status": 404})
    events_resource.delete.return_value.execute.side_effect = HttpError(resp, b"Not Found")

    client = GoogleCalClient(service=service, calendar_id="work@gmail.com")
    # Should not raise
    client.delete_busy_block("gid-deleted")


def test_make_body_full_details():
    service, events_resource = _mock_service()
    events_resource.insert.return_value.execute.return_value = {"id": "gid-new"}

    client = GoogleCalClient(service=service, calendar_id="work@gmail.com")
    event = Event(
        uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T11:00:00+00:00",
        all_day=False, title="Team standup", location="Room 3B", description="Daily sync",
    )
    client.create_event(event, busy_only=False)

    body = events_resource.insert.call_args[1]["body"]
    assert body["summary"] == "Team standup"
    assert body["location"] == "Room 3B"
    assert body["description"] == "Daily sync"


def test_make_body_busy_only():
    service, events_resource = _mock_service()
    events_resource.insert.return_value.execute.return_value = {"id": "gid-new"}

    client = GoogleCalClient(service=service, calendar_id="work@gmail.com")
    event = Event(
        uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T11:00:00+00:00",
        all_day=False, title="Team standup", location="Room 3B", description="Daily sync",
    )
    client.create_event(event, busy_only=True)

    body = events_resource.insert.call_args[1]["body"]
    assert body["summary"] == "Busy"
    assert "location" not in body
    assert body["description"] == ""


def test_make_body_full_details_omits_empty_fields():
    service, events_resource = _mock_service()
    events_resource.insert.return_value.execute.return_value = {"id": "gid-new"}

    client = GoogleCalClient(service=service, calendar_id="work@gmail.com")
    event = Event(
        uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T11:00:00+00:00",
        all_day=False, title="Meeting",
    )
    client.create_event(event, busy_only=False)

    body = events_resource.insert.call_args[1]["body"]
    assert body["summary"] == "Meeting"
    assert "location" not in body
    assert body["description"] == ""


def test_list_owned_calendars():
    service = MagicMock()
    service.calendarList.return_value.list.return_value.execute.return_value = {
        "items": [
            {"id": "primary@gmail.com", "summary": "Primary", "accessRole": "owner"},
            {"id": "work@group.calendar.google.com", "summary": "Work", "accessRole": "owner"},
            {"id": "shared@group.calendar.google.com", "summary": "Shared", "accessRole": "reader"},
        ]
    }

    calendars = list_owned_calendars(service)

    assert len(calendars) == 2
    assert calendars[0] == {"id": "primary@gmail.com", "name": "Primary"}
    assert calendars[1] == {"id": "work@group.calendar.google.com", "name": "Work"}


def test_list_owned_calendars_empty():
    service = MagicMock()
    service.calendarList.return_value.list.return_value.execute.return_value = {"items": []}

    calendars = list_owned_calendars(service)
    assert calendars == []
