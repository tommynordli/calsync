import logging
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from cal_sync.diff import Event

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


class GoogleCalClient:
    def __init__(self, service, calendar_id: str):
        self.service = service
        self.calendar_id = calendar_id

    def _make_body(self, event: Event) -> dict:
        body = {
            "summary": "Busy",
            "transparency": "opaque",
            "description": "",
            "extendedProperties": {
                "private": {"icloud_uid": event.uid},
            },
        }
        if event.all_day:
            body["start"] = {"date": event.start}
            body["end"] = {"date": event.end}
        else:
            body["start"] = {"dateTime": event.start}
            body["end"] = {"dateTime": event.end}
        return body

    def create_busy_block(self, event: Event) -> str:
        body = self._make_body(event)
        result = self.service.events().insert(
            calendarId=self.calendar_id, body=body
        ).execute()
        logger.info("Created busy block: %s", result["id"])
        return result["id"]

    def update_busy_block(self, google_event_id: str, event: Event):
        body = self._make_body(event)
        self.service.events().update(
            calendarId=self.calendar_id, eventId=google_event_id, body=body
        ).execute()
        logger.info("Updated busy block: %s", google_event_id)

    def delete_busy_block(self, google_event_id: str):
        self.service.events().delete(
            calendarId=self.calendar_id, eventId=google_event_id
        ).execute()
        logger.info("Deleted busy block: %s", google_event_id)
