# tests/test_icloud_write.py
from unittest.mock import MagicMock, patch
from calsync.icloud_write import (
    get_target_calendar, _make_vcalendar, create_icloud_event,
    update_icloud_event, delete_icloud_event,
)
from calsync.diff import Event


def test_make_vcalendar_busy_only():
    event = Event(uid="gid-123", start="2026-03-01T10:00:00+00:00",
                  end="2026-03-01T11:00:00+00:00", all_day=False,
                  title="Team standup", location="Room 3B", description="Daily sync")
    vcal = _make_vcalendar(event, busy_only=True)

    assert "SUMMARY:Busy" in vcal
    assert "Team standup" not in vcal
    assert "Room 3B" not in vcal
    assert "Daily sync" not in vcal
    assert "X-CALSYNC-SOURCE:google" in vcal
    assert "UID:calsync-reverse-gid-123" in vcal


def test_make_vcalendar_full_details():
    event = Event(uid="gid-123", start="2026-03-01T10:00:00+00:00",
                  end="2026-03-01T11:00:00+00:00", all_day=False,
                  title="Team standup", location="Room 3B", description="Daily sync")
    vcal = _make_vcalendar(event, busy_only=False)

    assert "SUMMARY:Team standup" in vcal
    assert "LOCATION:Room 3B" in vcal
    assert "DESCRIPTION:Daily sync" in vcal
    assert "X-CALSYNC-SOURCE:google" in vcal


def test_make_vcalendar_all_day():
    event = Event(uid="gid-456", start="2026-03-01", end="2026-03-02", all_day=True)
    vcal = _make_vcalendar(event, busy_only=True)

    assert "DTSTART;VALUE=DATE:20260301" in vcal
    assert "DTEND;VALUE=DATE:20260302" in vcal


def test_make_vcalendar_no_location_or_description():
    event = Event(uid="gid-789", start="2026-03-01T10:00:00+00:00",
                  end="2026-03-01T11:00:00+00:00", all_day=False,
                  title="Quick chat")
    vcal = _make_vcalendar(event, busy_only=False)

    assert "SUMMARY:Quick chat" in vcal
    assert "LOCATION:" not in vcal
    assert "DESCRIPTION:" not in vcal


def test_make_vcalendar_utc_z_suffix():
    """Google API returns UTC times with Z suffix."""
    event = Event(uid="gid-100", start="2026-03-01T10:00:00Z",
                  end="2026-03-01T11:00:00Z", all_day=False, title="Meeting")
    vcal = _make_vcalendar(event, busy_only=False)

    assert "DTSTART:20260301T100000Z" in vcal
    assert "DTEND:20260301T110000Z" in vcal


def test_make_vcalendar_utc_plus_zero_offset():
    """Handle +00:00 offset (e.g. from Python isoformat)."""
    event = Event(uid="gid-101", start="2026-03-01T10:00:00+00:00",
                  end="2026-03-01T11:00:00+00:00", all_day=False, title="Meeting")
    vcal = _make_vcalendar(event, busy_only=False)

    assert "DTSTART:20260301T100000Z" in vcal
    assert "DTEND:20260301T110000Z" in vcal


def test_make_vcalendar_positive_offset():
    """Non-UTC positive offset should be converted to UTC."""
    event = Event(uid="gid-102", start="2026-03-01T10:00:00+05:30",
                  end="2026-03-01T11:00:00+05:30", all_day=False, title="Meeting")
    vcal = _make_vcalendar(event, busy_only=False)

    assert "DTSTART:20260301T043000Z" in vcal
    assert "DTEND:20260301T053000Z" in vcal


def test_make_vcalendar_negative_offset():
    """Non-UTC negative offset should be converted to UTC."""
    event = Event(uid="gid-103", start="2026-03-01T10:00:00-05:00",
                  end="2026-03-01T11:00:00-05:00", all_day=False, title="Meeting")
    vcal = _make_vcalendar(event, busy_only=False)

    assert "DTSTART:20260301T150000Z" in vcal
    assert "DTEND:20260301T160000Z" in vcal


def test_make_vcalendar_escapes_newlines():
    """Newlines in description must be escaped to \\n per RFC 5545."""
    event = Event(uid="gid-200", start="2026-03-01T10:00:00+00:00",
                  end="2026-03-01T11:00:00+00:00", all_day=False,
                  title="Planning", description="Line one\nLine two\nLine three")
    vcal = _make_vcalendar(event, busy_only=False)

    assert "DESCRIPTION:Line one\\nLine two\\nLine three" in vcal
    # Raw newline must NOT appear inside a property value
    for line in vcal.split("\r\n"):
        if line.startswith("DESCRIPTION:"):
            assert "\n" not in line


def test_make_vcalendar_escapes_special_chars():
    """Backslashes, semicolons, and commas must be escaped per RFC 5545."""
    event = Event(uid="gid-201", start="2026-03-01T10:00:00+00:00",
                  end="2026-03-01T11:00:00+00:00", all_day=False,
                  title="A; B, C", location="Room\\Floor 2",
                  description="x;y,z")
    vcal = _make_vcalendar(event, busy_only=False)

    assert "SUMMARY:A\\; B\\, C" in vcal
    assert "LOCATION:Room\\\\Floor 2" in vcal
    assert "DESCRIPTION:x\\;y\\,z" in vcal


def test_create_icloud_event():
    calendar = MagicMock()
    created = MagicMock()
    created.url = "https://caldav.icloud.com/123/event.ics"
    calendar.save_event.return_value = created

    event = Event(uid="gid-123", start="2026-03-01T10:00:00+00:00",
                  end="2026-03-01T11:00:00+00:00", all_day=False)

    href = create_icloud_event(calendar, event, busy_only=True)

    assert href == "https://caldav.icloud.com/123/event.ics"
    calendar.save_event.assert_called_once()
    vcal_arg = calendar.save_event.call_args[0][0]
    assert "X-CALSYNC-SOURCE:google" in vcal_arg


def test_update_icloud_event():
    calendar = MagicMock()
    existing = MagicMock()
    calendar.event_by_url.return_value = existing

    event = Event(uid="gid-123", start="2026-03-01T10:00:00+00:00",
                  end="2026-03-01T12:00:00+00:00", all_day=False, title="Updated")

    update_icloud_event(calendar, "https://caldav.icloud.com/123/event.ics", event, busy_only=False)

    calendar.event_by_url.assert_called_once_with("https://caldav.icloud.com/123/event.ics")
    existing.save.assert_called_once()
    assert "SUMMARY:Updated" in existing.data


def test_delete_icloud_event():
    calendar = MagicMock()
    existing = MagicMock()
    calendar.event_by_url.return_value = existing

    delete_icloud_event(calendar, "https://caldav.icloud.com/123/event.ics")

    existing.delete.assert_called_once()


def test_delete_icloud_event_already_gone():
    calendar = MagicMock()
    calendar.event_by_url.side_effect = Exception("404 Not Found")

    # Should not raise
    delete_icloud_event(calendar, "https://caldav.icloud.com/123/event.ics")


@patch("calsync.icloud_write.caldav.DAVClient")
def test_get_target_calendar(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_principal = MagicMock()
    mock_client.principal.return_value = mock_principal

    cal1 = MagicMock()
    cal1.name = "Personal"
    cal2 = MagicMock()
    cal2.name = "Work Events"
    mock_principal.calendars.return_value = [cal1, cal2]

    result = get_target_calendar("test@icloud.com", "password", "Work Events")
    assert result == cal2


@patch("calsync.icloud_write.caldav.DAVClient")
def test_get_target_calendar_not_found(mock_client_class):
    import pytest

    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_principal = MagicMock()
    mock_client.principal.return_value = mock_principal

    cal1 = MagicMock()
    cal1.name = "Personal"
    mock_principal.calendars.return_value = [cal1]

    with pytest.raises(ValueError, match="No iCloud calendar found"):
        get_target_calendar("test@icloud.com", "password", "Nonexistent")
