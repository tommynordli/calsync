# calsync/icloud_write.py
import logging
from datetime import datetime, timezone

import caldav

from calsync.diff import Event
from calsync.icloud import ICLOUD_CALDAV_URL

logger = logging.getLogger(__name__)


def get_target_calendar(
    username: str,
    app_password: str,
    calendar_name: str,
) -> caldav.Calendar:
    client = caldav.DAVClient(
        url=ICLOUD_CALDAV_URL,
        username=username,
        password=app_password,
    )
    principal = client.principal()
    calendars = principal.calendars()

    for cal in calendars:
        if cal.name == calendar_name:
            return cal

    available = [c.name for c in calendars]
    raise ValueError(
        f"No iCloud calendar found named '{calendar_name}'. Available: {available}"
    )


def _ical_escape(text: str) -> str:
    """Escape TEXT values per RFC 5545 Section 3.3.11."""
    return (text
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
        .replace("\r", ""))


def _to_ical_datetime(iso_str: str) -> str:
    """Convert ISO 8601 / RFC 3339 datetime string to iCalendar basic format in UTC."""
    normalized = iso_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y%m%dT%H%M%SZ")


def _make_vcalendar(event: Event, busy_only: bool) -> str:
    uid = f"calsync-reverse-{event.uid}"

    if busy_only:
        summary = "Busy"
        description = ""
        location = ""
    else:
        summary = event.title or "Busy"
        description = event.description
        location = event.location

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//calsync//EN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
    ]

    if event.all_day:
        lines.append(f"DTSTART;VALUE=DATE:{event.start.replace('-', '')}")
        lines.append(f"DTEND;VALUE=DATE:{event.end.replace('-', '')}")
    else:
        lines.append(f"DTSTART:{_to_ical_datetime(event.start)}")
        lines.append(f"DTEND:{_to_ical_datetime(event.end)}")

    lines.append(f"SUMMARY:{_ical_escape(summary)}")
    if description:
        lines.append(f"DESCRIPTION:{_ical_escape(description)}")
    if location:
        lines.append(f"LOCATION:{_ical_escape(location)}")
    lines.append("X-CALSYNC-SOURCE:google")
    lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")

    return "\r\n".join(lines)


def create_icloud_event(
    calendar: caldav.Calendar,
    event: Event,
    busy_only: bool,
) -> str:
    vcal = _make_vcalendar(event, busy_only)
    created = calendar.save_event(vcal)
    logger.info("Created iCloud event for Google ID: %s", event.uid)
    return str(created.url)


def update_icloud_event(
    calendar: caldav.Calendar,
    event_href: str,
    event: Event,
    busy_only: bool,
) -> None:
    vcal = _make_vcalendar(event, busy_only)
    existing = calendar.event_by_url(event_href)
    existing.data = vcal
    existing.save()
    logger.info("Updated iCloud event: %s", event_href)


def delete_icloud_event(
    calendar: caldav.Calendar,
    event_href: str,
) -> None:
    try:
        existing = calendar.event_by_url(event_href)
        existing.delete()
        logger.info("Deleted iCloud event: %s", event_href)
    except Exception as e:
        if "404" in str(e) or "NotFound" in type(e).__name__:
            logger.warning("iCloud event already deleted: %s", event_href)
        else:
            raise
