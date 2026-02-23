# iCloud to Google Calendar Sync — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Sync two personal iCloud calendars to a Google work calendar as "Busy" blocks, running every 15 minutes on macOS.

**Architecture:** A single Python package (`cal_sync/`) with modules for config, iCloud fetching, Google Calendar pushing, state tracking, and diff logic. A CLI entry point handles auth and sync. Scheduled via macOS launchd.

**Tech Stack:** Python 3.11+, caldav, google-api-python-client, google-auth-oauthlib, pyyaml, pytest

**Design doc:** `docs/plans/2026-02-23-ical-to-gcal-sync-design.md`

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `cal_sync/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `config.yaml.example`
- Create: `.gitignore`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "cal-sync"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "caldav>=1.3",
    "google-api-python-client>=2.100",
    "google-auth-oauthlib>=1.1",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-mock>=3.12"]

[project.scripts]
cal-sync = "cal_sync.cli:main"
```

**Step 2: Create directory structure and empty inits**

```python
# cal_sync/__init__.py
# (empty)
```

```python
# tests/__init__.py
# (empty)
```

```python
# tests/conftest.py
import pytest
```

**Step 3: Create config.yaml.example**

```yaml
icloud:
  username: "your@icloud.com"
  app_password: "xxxx-xxxx-xxxx-xxxx"
  calendars:
    - "Personal"
    - "Family"

google:
  calendar_id: "your.work@gmail.com"
  credentials_file: "credentials.json"
  token_file: "token.json"

sync:
  lookahead_days: 30
```

**Step 4: Create .gitignore**

```
__pycache__/
*.egg-info/
.venv/
config.yaml
credentials.json
token.json
state.json
*.pyc
```

**Step 5: Install the project**

Run: `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
Expected: clean install, no errors

**Step 6: Commit**

```bash
git add pyproject.toml cal_sync/__init__.py tests/__init__.py tests/conftest.py config.yaml.example .gitignore
git commit -m "feat: project scaffolding with dependencies"
```

---

### Task 2: Config Loading

**Files:**
- Create: `cal_sync/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
# tests/test_config.py
from pathlib import Path
from cal_sync.config import load_config


def test_load_config(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
icloud:
  username: "test@icloud.com"
  app_password: "abcd-efgh-ijkl-mnop"
  calendars:
    - "Personal"
    - "Family"
google:
  calendar_id: "work@gmail.com"
  credentials_file: "creds.json"
  token_file: "tok.json"
sync:
  lookahead_days: 14
""")
    config = load_config(config_file)
    assert config.icloud_username == "test@icloud.com"
    assert config.icloud_app_password == "abcd-efgh-ijkl-mnop"
    assert config.icloud_calendars == ["Personal", "Family"]
    assert config.google_calendar_id == "work@gmail.com"
    assert config.google_credentials_file == Path("creds.json")
    assert config.google_token_file == Path("tok.json")
    assert config.lookahead_days == 14


def test_load_config_defaults(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
icloud:
  username: "test@icloud.com"
  app_password: "abcd-efgh-ijkl-mnop"
  calendars:
    - "Cal1"
google:
  calendar_id: "work@gmail.com"
  credentials_file: "creds.json"
  token_file: "tok.json"
""")
    config = load_config(config_file)
    assert config.lookahead_days == 30


def test_load_config_missing_file():
    import pytest
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/config.yaml"))
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError` or `ImportError`

**Step 3: Write minimal implementation**

```python
# cal_sync/config.py
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Config:
    icloud_username: str
    icloud_app_password: str
    icloud_calendars: list[str]
    google_calendar_id: str
    google_credentials_file: Path
    google_token_file: Path
    lookahead_days: int


def load_config(path: Path) -> Config:
    with open(path) as f:
        raw = yaml.safe_load(f)

    icloud = raw["icloud"]
    google = raw["google"]
    sync = raw.get("sync", {})

    return Config(
        icloud_username=icloud["username"],
        icloud_app_password=icloud["app_password"],
        icloud_calendars=icloud["calendars"],
        google_calendar_id=google["calendar_id"],
        google_credentials_file=Path(google["credentials_file"]),
        google_token_file=Path(google["token_file"]),
        lookahead_days=sync.get("lookahead_days", 30),
    )
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add cal_sync/config.py tests/test_config.py
git commit -m "feat: config loading from YAML"
```

---

### Task 3: State Management

**Files:**
- Create: `cal_sync/state.py`
- Create: `tests/test_state.py`

**Step 1: Write the failing tests**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_state.py -v`
Expected: FAIL — `ImportError`

**Step 3: Write minimal implementation**

```python
# cal_sync/state.py
import json
from pathlib import Path


class SyncState:
    def __init__(self, path: Path):
        self.path = path
        if path.exists():
            with open(path) as f:
                self.entries: dict[str, dict] = json.load(f)
        else:
            self.entries = {}

    def set(self, icloud_uid: str, google_event_id: str, start: str, end: str, all_day: bool):
        self.entries[icloud_uid] = {
            "google_event_id": google_event_id,
            "start": start,
            "end": end,
            "all_day": all_day,
        }

    def remove(self, icloud_uid: str):
        self.entries.pop(icloud_uid, None)

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.entries, f, indent=2)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_state.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add cal_sync/state.py tests/test_state.py
git commit -m "feat: state management with JSON persistence"
```

---

### Task 4: Diff Logic

**Files:**
- Create: `cal_sync/diff.py`
- Create: `tests/test_diff.py`

**Step 1: Write the failing tests**

```python
# tests/test_diff.py
from cal_sync.diff import Event, compute_diff


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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_diff.py -v`
Expected: FAIL — `ImportError`

**Step 3: Write minimal implementation**

```python
# cal_sync/diff.py
from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    uid: str
    start: str
    end: str
    all_day: bool


def compute_diff(
    events: list[Event],
    state_entries: dict[str, dict],
) -> tuple[list[Event], list[tuple[Event, str]], list[tuple[str, str]]]:
    current_uids = {e.uid for e in events}
    events_by_uid = {e.uid: e for e in events}

    to_create: list[Event] = []
    to_update: list[tuple[Event, str]] = []
    to_delete: list[tuple[str, str]] = []

    for event in events:
        if event.uid not in state_entries:
            to_create.append(event)
        else:
            entry = state_entries[event.uid]
            if event.start != entry["start"] or event.end != entry["end"] or event.all_day != entry["all_day"]:
                to_update.append((event, entry["google_event_id"]))

    for uid, entry in state_entries.items():
        if uid not in current_uids:
            to_delete.append((uid, entry["google_event_id"]))

    return to_create, to_update, to_delete
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_diff.py -v`
Expected: 5 passed

**Step 5: Commit**

```bash
git add cal_sync/diff.py tests/test_diff.py
git commit -m "feat: diff logic for create/update/delete"
```

---

### Task 5: iCloud CalDAV Client

**Files:**
- Create: `cal_sync/icloud.py`
- Create: `tests/test_icloud.py`

**Step 1: Write the failing tests**

These tests mock the `caldav` library since we can't hit iCloud in tests.

```python
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_icloud.py -v`
Expected: FAIL — `ImportError`

**Step 3: Write minimal implementation**

```python
# cal_sync/icloud.py
import logging
from datetime import date, datetime, timedelta, timezone

import caldav

from cal_sync.diff import Event

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
                event = _parse_vevent(vevent)
                if event:
                    events.append(event)
            except Exception:
                logger.exception("Failed to parse event from calendar '%s'", cal.name)

    return events


def _parse_vevent(vevent) -> Event | None:
    contents = vevent.contents

    status = None
    if "status" in contents:
        status = contents["status"][0].value
    if status and status.upper() == "CANCELLED":
        return None

    uid = contents["uid"][0].value
    dtstart = contents["dtstart"][0].value
    dtend = contents["dtend"][0].value if "dtend" in contents else None

    all_day = isinstance(dtstart, date) and not isinstance(dtstart, datetime)

    if all_day:
        start_str = dtstart.isoformat()
        end_str = dtend.isoformat() if dtend else (dtstart + timedelta(days=1)).isoformat()
    else:
        start_str = dtstart.isoformat()
        end_str = dtend.isoformat() if dtend else start_str

    return Event(uid=uid, start=start_str, end=end_str, all_day=all_day)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_icloud.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add cal_sync/icloud.py tests/test_icloud.py
git commit -m "feat: iCloud CalDAV event fetching"
```

---

### Task 6: Google Calendar Client

**Files:**
- Create: `cal_sync/google_cal.py`
- Create: `tests/test_google_cal.py`

**Step 1: Write the failing tests**

```python
# tests/test_google_cal.py
from unittest.mock import MagicMock, patch
from pathlib import Path
from cal_sync.google_cal import GoogleCalClient
from cal_sync.diff import Event


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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_google_cal.py -v`
Expected: FAIL — `ImportError`

**Step 3: Write minimal implementation**

```python
# cal_sync/google_cal.py
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
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_google_cal.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add cal_sync/google_cal.py tests/test_google_cal.py
git commit -m "feat: Google Calendar client for busy blocks"
```

---

### Task 7: Sync Orchestration

**Files:**
- Create: `cal_sync/sync.py`
- Create: `tests/test_sync.py`

**Step 1: Write the failing tests**

```python
# tests/test_sync.py
from unittest.mock import MagicMock
from cal_sync.sync import run_sync
from cal_sync.diff import Event
from cal_sync.state import SyncState


def test_sync_creates_new_events(tmp_path):
    state = SyncState(tmp_path / "state.json")
    gcal = MagicMock()
    gcal.create_busy_block.return_value = "gid-new"

    events = [Event(uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T11:00:00+00:00", all_day=False)]

    run_sync(events, state, gcal)

    gcal.create_busy_block.assert_called_once()
    state_reloaded = SyncState(tmp_path / "state.json")
    assert "uid-1" in state_reloaded.entries


def test_sync_updates_changed_events(tmp_path):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00+00:00", "2026-03-01T11:00:00+00:00", False)
    state.save()

    gcal = MagicMock()
    events = [Event(uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T12:00:00+00:00", all_day=False)]

    run_sync(events, state, gcal)

    gcal.update_busy_block.assert_called_once_with("gid-1", events[0])


def test_sync_deletes_removed_events(tmp_path):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00+00:00", "2026-03-01T11:00:00+00:00", False)
    state.save()

    gcal = MagicMock()
    events = []

    run_sync(events, state, gcal)

    gcal.delete_busy_block.assert_called_once_with("gid-1")
    state_reloaded = SyncState(tmp_path / "state.json")
    assert "uid-1" not in state_reloaded.entries
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sync.py -v`
Expected: FAIL — `ImportError`

**Step 3: Write minimal implementation**

```python
# cal_sync/sync.py
import logging

from cal_sync.diff import Event, compute_diff
from cal_sync.google_cal import GoogleCalClient
from cal_sync.state import SyncState

logger = logging.getLogger(__name__)


def run_sync(events: list[Event], state: SyncState, gcal: GoogleCalClient):
    to_create, to_update, to_delete = compute_diff(events, state.entries)

    logger.info("Sync: %d create, %d update, %d delete", len(to_create), len(to_update), len(to_delete))

    for event in to_create:
        google_id = gcal.create_busy_block(event)
        state.set(event.uid, google_id, event.start, event.end, event.all_day)

    for event, google_id in to_update:
        gcal.update_busy_block(google_id, event)
        state.set(event.uid, google_id, event.start, event.end, event.all_day)

    for icloud_uid, google_id in to_delete:
        gcal.delete_busy_block(google_id)
        state.remove(icloud_uid)

    state.save()
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sync.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add cal_sync/sync.py tests/test_sync.py
git commit -m "feat: sync orchestration with diff-based updates"
```

---

### Task 8: CLI Entry Point

**Files:**
- Create: `cal_sync/cli.py`

**Step 1: Write the CLI**

No TDD here — this is the thin wiring layer that connects all the tested components.

```python
# cal_sync/cli.py
import argparse
import logging
import sys
from pathlib import Path

from cal_sync.config import load_config
from cal_sync.google_cal import GoogleCalClient, authenticate, build_service
from cal_sync.icloud import fetch_icloud_events
from cal_sync.state import SyncState
from cal_sync.sync import run_sync

LOG_DIR = Path.home() / ".local" / "log"
LOG_FILE = LOG_DIR / "cal-sync.log"


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(),
        ],
    )


def main():
    parser = argparse.ArgumentParser(description="Sync iCloud calendars to Google Calendar as busy blocks")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"), help="Path to config file")
    parser.add_argument("--state", type=Path, default=Path("state.json"), help="Path to state file")
    parser.add_argument("--auth", action="store_true", help="Run OAuth flow and exit")
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger(__name__)

    config = load_config(args.config)

    if args.auth:
        logger.info("Running Google OAuth authentication flow...")
        authenticate(config.google_credentials_file, config.google_token_file)
        logger.info("Authentication complete. Token saved to %s", config.google_token_file)
        return

    logger.info("Starting sync...")
    try:
        creds = authenticate(config.google_credentials_file, config.google_token_file)
        service = build_service(creds)
        gcal = GoogleCalClient(service=service, calendar_id=config.google_calendar_id)

        events = fetch_icloud_events(
            username=config.icloud_username,
            app_password=config.icloud_app_password,
            calendar_names=config.icloud_calendars,
            lookahead_days=config.lookahead_days,
        )
        logger.info("Fetched %d events from iCloud", len(events))

        state = SyncState(args.state)
        run_sync(events, state, gcal)
        logger.info("Sync complete")
    except Exception:
        logger.exception("Sync failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Step 2: Verify all tests still pass**

Run: `python -m pytest -v`
Expected: All 14 tests pass

**Step 3: Commit**

```bash
git add cal_sync/cli.py
git commit -m "feat: CLI entry point with auth and sync commands"
```

---

### Task 9: launchd Plist & README

**Files:**
- Create: `com.cal-sync.plist`
- Create: `README.md`

**Step 1: Create the launchd plist**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cal-sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>VENV_PATH/bin/cal-sync</string>
        <string>--config</string>
        <string>PROJECT_PATH/config.yaml</string>
        <string>--state</string>
        <string>PROJECT_PATH/state.json</string>
    </array>
    <key>WorkingDirectory</key>
    <string>PROJECT_PATH</string>
    <key>StartInterval</key>
    <integer>900</integer>
    <key>StandardOutPath</key>
    <string>LOG_PATH/cal-sync-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>LOG_PATH/cal-sync-stderr.log</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

**Step 2: Create README.md**

Document:
- What the tool does (one paragraph)
- Prerequisites (Python 3.11+, iCloud app-specific password, Google Cloud project)
- Setup steps (numbered, with links to Apple and Google docs)
- How to install the launchd plist (with `sed` commands to replace `PROJECT_PATH`, `VENV_PATH`, `LOG_PATH`)
- How to check logs
- How to uninstall

**Step 3: Commit**

```bash
git add com.cal-sync.plist README.md
git commit -m "docs: launchd plist and README with setup instructions"
```

---

### Task 10: Run Full Test Suite & Manual Smoke Test

**Step 1: Run all tests**

Run: `python -m pytest -v`
Expected: All 14 tests pass

**Step 2: Manual smoke test (with real credentials)**

Run: `python -m cal_sync.cli --config config.yaml --auth`
Expected: Browser opens for Google OAuth consent, token saved

Run: `python -m cal_sync.cli --config config.yaml`
Expected: Events fetched from iCloud, busy blocks created on Google Calendar

**Step 3: Final commit if any fixes needed**
