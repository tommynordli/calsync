# tests/test_icloud.py
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from cal_sync.icloud import fetch_icloud_events
from cal_sync.diff import Event


def _make_mock_vevent(uid, dtstart, dtend, status="CONFIRMED"):
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

    return vevent


def _make_mock_caldav_event(uid, dtstart, dtend, status="CONFIRMED"):
    event = MagicMock()
    vevent = _make_mock_vevent(uid, dtstart, dtend, status)
    event.vobject_instance.vevent = vevent
    return event


@patch("cal_sync.icloud.caldav.DAVClient")
def test_fetch_events_basic(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_principal = MagicMock()
    mock_client.principal.return_value = mock_principal

    cal = MagicMock()
    cal.name = "Personal"
    dt1 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    dt2 = datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc)
    cal.search.return_value = [_make_mock_caldav_event("uid-1", dt1, dt2)]
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


@patch("cal_sync.icloud.caldav.DAVClient")
def test_fetch_skips_cancelled(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_principal = MagicMock()
    mock_client.principal.return_value = mock_principal

    cal = MagicMock()
    cal.name = "Personal"
    dt1 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    dt2 = datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc)
    cal.search.return_value = [_make_mock_caldav_event("uid-1", dt1, dt2, status="CANCELLED")]
    mock_principal.calendars.return_value = [cal]

    events = fetch_icloud_events(
        username="test@icloud.com",
        app_password="password",
        calendar_names=["Personal"],
        lookahead_days=30,
    )

    assert len(events) == 0
