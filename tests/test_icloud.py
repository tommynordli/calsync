# tests/test_icloud.py
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from calsync.icloud import fetch_icloud_events
from calsync.diff import Event


def _make_mock_vevent(uid, dtstart, dtend, status="CONFIRMED", title=None, location=None, description=None):
    vevent = MagicMock()
    vevent.contents = {}
    uid_component = MagicMock()
    uid_component.value = uid
    vevent.contents["uid"] = [uid_component]

    start_component = MagicMock()
    start_component.value = dtstart
    vevent.contents["dtstart"] = [start_component]

    end_component = MagicMock()
    end_component.value = dtend
    vevent.contents["dtend"] = [end_component]

    if status:
        status_component = MagicMock()
        status_component.value = status
        vevent.contents["status"] = [status_component]

    if title is not None:
        summary_component = MagicMock()
        summary_component.value = title
        vevent.contents["summary"] = [summary_component]

    if location is not None:
        location_component = MagicMock()
        location_component.value = location
        vevent.contents["location"] = [location_component]

    if description is not None:
        desc_component = MagicMock()
        desc_component.value = description
        vevent.contents["description"] = [desc_component]

    return vevent


def _make_mock_caldav_event(uid, dtstart, dtend, status="CONFIRMED", title=None, location=None, description=None):
    event = MagicMock()
    vevent = _make_mock_vevent(uid, dtstart, dtend, status, title, location, description)
    event.vobject_instance.vevent = vevent
    return event


@patch("calsync.icloud.caldav.DAVClient")
def test_fetch_events_basic(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_principal = MagicMock()
    mock_client.principal.return_value = mock_principal

    cal = MagicMock()
    cal.name = "Personal"
    dt1 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    dt2 = datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc)
    cal.date_search.return_value = [_make_mock_caldav_event("uid-1", dt1, dt2)]
    mock_principal.calendars.return_value = [cal]

    events = fetch_icloud_events(
        username="test@icloud.com",
        app_password="password",
        calendar_names=["Personal"],
        lookahead_days=30,
    )

    assert len(events) == 1
    assert events[0].uid == "uid-1"
    assert events[0].all_day is False


@patch("calsync.icloud.caldav.DAVClient")
def test_fetch_skips_cancelled(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_principal = MagicMock()
    mock_client.principal.return_value = mock_principal

    cal = MagicMock()
    cal.name = "Personal"
    dt1 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    dt2 = datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc)
    cal.date_search.return_value = [_make_mock_caldav_event("uid-1", dt1, dt2, status="CANCELLED")]
    mock_principal.calendars.return_value = [cal]

    events = fetch_icloud_events(
        username="test@icloud.com",
        app_password="password",
        calendar_names=["Personal"],
        lookahead_days=30,
    )

    assert len(events) == 0


@patch("calsync.icloud.caldav.DAVClient")
def test_fetch_recurring_events_unique_uids(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_principal = MagicMock()
    mock_client.principal.return_value = mock_principal

    cal = MagicMock()
    cal.name = "Personal"

    # Two occurrences of same recurring event (same base UID)
    dt1 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    dt2 = datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc)
    dt3 = datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc)
    dt4 = datetime(2026, 3, 8, 11, 0, tzinfo=timezone.utc)

    event1 = _make_mock_caldav_event("recurring-uid", dt1, dt2)
    # Add recurrence-id to first occurrence
    rid1 = MagicMock()
    rid1.value = dt1
    event1.vobject_instance.vevent.contents["recurrence-id"] = [rid1]

    event2 = _make_mock_caldav_event("recurring-uid", dt3, dt4)
    rid2 = MagicMock()
    rid2.value = dt3
    event2.vobject_instance.vevent.contents["recurrence-id"] = [rid2]

    cal.date_search.return_value = [event1, event2]
    mock_principal.calendars.return_value = [cal]

    events = fetch_icloud_events(
        username="test@icloud.com",
        app_password="password",
        calendar_names=["Personal"],
        lookahead_days=30,
    )

    assert len(events) == 2
    assert events[0].uid != events[1].uid  # UIDs should be unique
    assert "recurring-uid" in events[0].uid
    assert "recurring-uid" in events[1].uid


@patch("calsync.icloud.caldav.DAVClient")
def test_fetch_extracts_event_details(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_principal = MagicMock()
    mock_client.principal.return_value = mock_principal

    cal = MagicMock()
    cal.name = "Personal"
    dt1 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    dt2 = datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc)
    cal.date_search.return_value = [
        _make_mock_caldav_event("uid-1", dt1, dt2, title="Lunch", location="Cafe", description="With Alex")
    ]
    mock_principal.calendars.return_value = [cal]

    events = fetch_icloud_events(
        username="test@icloud.com",
        app_password="password",
        calendar_names=["Personal"],
        lookahead_days=30,
    )

    assert events[0].title == "Lunch"
    assert events[0].location == "Cafe"
    assert events[0].description == "With Alex"


@patch("calsync.icloud.caldav.DAVClient")
def test_fetch_skips_calsync_source_google(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_principal = MagicMock()
    mock_client.principal.return_value = mock_principal

    cal = MagicMock()
    cal.name = "Work Events"
    dt1 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    dt2 = datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc)

    # Event with X-CALSYNC-SOURCE (created by reverse sync)
    event_with_source = _make_mock_caldav_event("calsync-reverse-gid-1", dt1, dt2)
    source_component = MagicMock()
    source_component.value = "google"
    event_with_source.vobject_instance.vevent.contents["x-calsync-source"] = [source_component]

    # Normal event without the marker
    normal_event = _make_mock_caldav_event("uid-2", dt1, dt2)

    cal.date_search.return_value = [event_with_source, normal_event]
    mock_principal.calendars.return_value = [cal]

    events = fetch_icloud_events(
        username="test@icloud.com",
        app_password="password",
        calendar_names=["Work Events"],
        lookahead_days=30,
    )

    assert len(events) == 1
    assert events[0].uid == "uid-2"


@patch("calsync.icloud.caldav.DAVClient")
def test_fetch_missing_details_default_empty(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_principal = MagicMock()
    mock_client.principal.return_value = mock_principal

    cal = MagicMock()
    cal.name = "Personal"
    dt1 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    dt2 = datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc)
    cal.date_search.return_value = [_make_mock_caldav_event("uid-1", dt1, dt2)]
    mock_principal.calendars.return_value = [cal]

    events = fetch_icloud_events(
        username="test@icloud.com",
        app_password="password",
        calendar_names=["Personal"],
        lookahead_days=30,
    )

    assert events[0].title == ""
    assert events[0].location == ""
    assert events[0].description == ""
