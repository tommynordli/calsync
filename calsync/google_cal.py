import logging
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from calsync.diff import Event

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def authenticate(credentials_file: Path, token_file: Path) -> Credentials:
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w") as f:
            f.write(creds.to_json())

    return creds


def build_service(creds: Credentials):
    return build("calendar", "v3", credentials=creds)


def list_owned_calendars(service) -> list[dict]:
    result = service.calendarList().list(minAccessRole="owner").execute()
    return [
        {"id": item["id"], "name": item["summary"]}
        for item in result.get("items", [])
        if item.get("accessRole") == "owner"
    ]


class GoogleCalClient:
    def __init__(self, service, calendar_id: str):
        self.service = service
        self.calendar_id = calendar_id

    def _make_body(self, event: Event, busy_only: bool = True) -> dict:
        if busy_only:
            body = {
                "summary": "Busy",
                "transparency": "opaque",
                "description": "",
                "extendedProperties": {
                    "private": {"icloud_uid": event.uid},
                },
            }
        else:
            body = {
                "summary": event.title or "Busy",
                "transparency": "opaque",
                "description": event.description,
                "extendedProperties": {
                    "private": {"icloud_uid": event.uid},
                },
            }
            if event.location:
                body["location"] = event.location

        if event.all_day:
            body["start"] = {"date": event.start}
            body["end"] = {"date": event.end}
        else:
            body["start"] = {"dateTime": event.start, "timeZone": "UTC"}
            body["end"] = {"dateTime": event.end, "timeZone": "UTC"}
        return body

    def create_event(self, event: Event, busy_only: bool = True) -> str:
        body = self._make_body(event, busy_only)
        result = self.service.events().insert(
            calendarId=self.calendar_id, body=body
        ).execute()
        logger.info("Created event: %s", result["id"])
        return result["id"]

    def update_event(self, google_event_id: str, event: Event, busy_only: bool = True):
        body = self._make_body(event, busy_only)
        self.service.events().update(
            calendarId=self.calendar_id, eventId=google_event_id, body=body
        ).execute()
        logger.info("Updated event: %s", google_event_id)

    def delete_event(self, google_event_id: str):
        try:
            self.service.events().delete(
                calendarId=self.calendar_id, eventId=google_event_id
            ).execute()
            logger.info("Deleted event: %s", google_event_id)
        except HttpError as e:
            if e.resp.status == 404:
                logger.warning("Event %s already deleted", google_event_id)
            else:
                raise

    # Aliases for backwards compatibility (removed in Task 12)
    create_busy_block = create_event
    update_busy_block = update_event
    delete_busy_block = delete_event
