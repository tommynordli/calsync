# calsync/icloud.py
import logging
from datetime import date, datetime, timedelta, timezone

import caldav

from calsync.diff import Event

logger = logging.getLogger(__name__)

ICLOUD_CALDAV_URL = "https://caldav.icloud.com"


def fetch_icloud_events(
    username: str,
    app_password: str,
    calendar_names: list[str],
    lookahead_days: int,
) -> list[Event]:
    client = caldav.DAVClient(
        url=ICLOUD_CALDAV_URL,
        username=username,
        password=app_password,
    )
    principal = client.principal()
    calendars = principal.calendars()

    target_cals = [c for c in calendars if c.name in calendar_names]
    if not target_cals:
        logger.warning("No matching calendars found. Available: %s", [c.name for c in calendars])
        return []

    now = datetime.now(timezone.utc)
    start = now
    end = now + timedelta(days=lookahead_days)

    events: list[Event] = []
    for cal in target_cals:
        logger.info("Fetching events from '%s'", cal.name)
        results = cal.search(start=start, end=end, event=True, expand=True)
        for item in results:
            try:
                vevent = item.vobject_instance.vevent
                event = _parse_vevent(vevent, username)
                if event:
                    events.append(event)
            except Exception:
                logger.exception("Failed to parse event from calendar '%s'", cal.name)

    return events


def _parse_vevent(vevent, owner_email: str = "") -> Event | None:
    contents = vevent.contents

    status = None
    if "status" in contents:
        status = contents["status"][0].value
    if status and status.upper() == "CANCELLED":
        return None

    # Loop prevention: skip events created by reverse sync
    if "x-calsync-source" in contents:
        return None

    # Skip events the user hasn't accepted (declined, tentative, no response)
    if owner_email and "attendee" in contents:
        owner_lower = owner_email.lower()
        for attendee in contents["attendee"]:
            email = attendee.value.lower().replace("mailto:", "")
            if owner_lower in email:
                partstat = attendee.params.get("PARTSTAT", [None])[0]
                if partstat and partstat.upper() != "ACCEPTED":
                    return None
                break

    uid = contents["uid"][0].value
    if "recurrence-id" in contents:
        recurrence_id = contents["recurrence-id"][0].value
        rid_str = recurrence_id.isoformat() if hasattr(recurrence_id, 'isoformat') else str(recurrence_id)
        uid = f"{uid}_{rid_str}"
    dtstart = contents["dtstart"][0].value
    dtend = contents["dtend"][0].value if "dtend" in contents else None

    all_day = isinstance(dtstart, date) and not isinstance(dtstart, datetime)

    if all_day:
        start_str = dtstart.isoformat()
        end_str = dtend.isoformat() if dtend else (dtstart + timedelta(days=1)).isoformat()
    else:
        start_str = dtstart.isoformat()
        end_str = dtend.isoformat() if dtend else start_str

    title = contents["summary"][0].value if "summary" in contents else ""
    location = contents["location"][0].value if "location" in contents else ""
    description = contents["description"][0].value if "description" in contents else ""

    return Event(uid=uid, start=start_str, end=end_str, all_day=all_day,
                 title=title, location=location, description=description)
