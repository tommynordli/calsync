# Calendar Selection & Full Event Sync — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users choose which Google Calendar to sync to, sync full event details by default, and handle calendar/mode switching gracefully.

**Architecture:** Extends the existing source→diff→sink pipeline. Event dataclass gains detail fields, `_make_body()` becomes mode-aware, state tracks metadata for switch detection. New Google API call (`calendarList.list`) for calendar enumeration. CLI gets `--calendar`, `--busy-only`, and `--purge` flags.

**Tech Stack:** Python 3.10+, Google Calendar API v3, pytest, caldav

---

### Task 1: Add detail fields to Event dataclass

**Files:**
- Modify: `calsync/diff.py:1-9`
- Test: `tests/test_diff.py`

**Step 1: Write the failing test**

Add to `tests/test_diff.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_diff.py::test_event_has_detail_fields tests/test_diff.py::test_event_detail_fields_default_empty -v`
Expected: FAIL — `Event.__init__()` doesn't accept title/location/description

**Step 3: Write minimal implementation**

In `calsync/diff.py`, update the `Event` dataclass:

```python
@dataclass(frozen=True)
class Event:
    uid: str
    start: str
    end: str
    all_day: bool
    title: str = ""
    location: str = ""
    description: str = ""
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_diff.py -v`
Expected: ALL PASS (existing tests still work because new fields have defaults)

**Step 5: Commit**

```bash
git add calsync/diff.py tests/test_diff.py
git commit -m "feat: add title, location, description fields to Event dataclass"
```

---

### Task 2: Extract event details from iCloud vevents

**Files:**
- Modify: `calsync/icloud.py:53-79` (`_parse_vevent`)
- Test: `tests/test_icloud.py`

**Step 1: Write the failing test**

Update `_make_mock_vevent` in `tests/test_icloud.py` to accept optional title, location, description kwargs. Add a new test:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_icloud.py::test_fetch_extracts_event_details tests/test_icloud.py::test_fetch_missing_details_default_empty -v`
Expected: FAIL — title/location/description not extracted

**Step 3: Write minimal implementation**

In `calsync/icloud.py`, update `_parse_vevent`:

```python
def _parse_vevent(vevent) -> Event | None:
    contents = vevent.contents

    status = None
    if "status" in contents:
        status = contents["status"][0].value
    if status and status.upper() == "CANCELLED":
        return None

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
```

**Step 4: Run all iCloud tests**

Run: `pytest tests/test_icloud.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add calsync/icloud.py tests/test_icloud.py
git commit -m "feat: extract title, location, description from iCloud vevents"
```

---

### Task 3: Add busy_only to Config

**Files:**
- Modify: `calsync/config.py`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_load_config_busy_only(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
icloud:
  username: "test@icloud.com"
  app_password: "abcd-efgh-ijkl-mnop"
  calendars:
    - "Personal"
google:
  calendar_id: "work@gmail.com"
  credentials_file: "creds.json"
  token_file: "tok.json"
sync:
  lookahead_days: 14
  busy_only: true
""")
    config = load_config(config_file)
    assert config.busy_only is True


def test_load_config_busy_only_defaults_false(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
icloud:
  username: "test@icloud.com"
  app_password: "abcd-efgh-ijkl-mnop"
  calendars:
    - "Personal"
google:
  calendar_id: "work@gmail.com"
  credentials_file: "creds.json"
  token_file: "tok.json"
""")
    config = load_config(config_file)
    assert config.busy_only is False
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py::test_load_config_busy_only tests/test_config.py::test_load_config_busy_only_defaults_false -v`
Expected: FAIL — Config has no `busy_only` attribute

**Step 3: Write minimal implementation**

In `calsync/config.py`:

```python
@dataclass(frozen=True)
class Config:
    icloud_username: str
    icloud_app_password: str
    icloud_calendars: list[str]
    google_calendar_id: str
    google_credentials_file: Path
    google_token_file: Path
    lookahead_days: int
    busy_only: bool
```

In `load_config`, add to the return statement:

```python
    return Config(
        icloud_username=icloud["username"],
        icloud_app_password=icloud["app_password"],
        icloud_calendars=icloud["calendars"],
        google_calendar_id=google["calendar_id"],
        google_credentials_file=_resolve(google["credentials_file"]),
        google_token_file=_resolve(google["token_file"]),
        lookahead_days=sync.get("lookahead_days", 30),
        busy_only=sync.get("busy_only", False),
    )
```

**Step 4: Run all config tests**

Run: `pytest tests/test_config.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add calsync/config.py tests/test_config.py
git commit -m "feat: add busy_only config option, defaults to false"
```

---

### Task 4: Update _make_body() for full details mode

**Files:**
- Modify: `calsync/google_cal.py:43-58`
- Test: `tests/test_google_cal.py`

**Step 1: Write the failing tests**

Add to `tests/test_google_cal.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_google_cal.py::test_make_body_full_details tests/test_google_cal.py::test_make_body_busy_only tests/test_google_cal.py::test_make_body_full_details_omits_empty_fields -v`
Expected: FAIL — `create_event` method doesn't exist

**Step 3: Write minimal implementation**

In `calsync/google_cal.py`, update the class. Rename `_make_body` to accept `busy_only`, rename public methods:

```python
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

    # Keep old names as aliases during transition
    create_busy_block = create_event
    update_busy_block = update_event
    delete_busy_block = delete_event
```

Note: keeping aliases `create_busy_block`/`update_busy_block`/`delete_busy_block` so existing callers and tests don't break. We'll update callers in Task 6.

**Step 4: Run all google_cal tests**

Run: `pytest tests/test_google_cal.py -v`
Expected: ALL PASS (old tests use aliases, new tests use new names)

**Step 5: Commit**

```bash
git add calsync/google_cal.py tests/test_google_cal.py
git commit -m "feat: add busy_only param to event body, support full details mode"
```

---

### Task 5: Add Google calendar listing function

**Files:**
- Modify: `calsync/google_cal.py`
- Test: `tests/test_google_cal.py`

**Step 1: Write the failing test**

Add to `tests/test_google_cal.py`:

```python
from calsync.google_cal import list_owned_calendars


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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_google_cal.py::test_list_owned_calendars tests/test_google_cal.py::test_list_owned_calendars_empty -v`
Expected: FAIL — `list_owned_calendars` doesn't exist

**Step 3: Write minimal implementation**

Add to `calsync/google_cal.py`:

```python
def list_owned_calendars(service) -> list[dict]:
    result = service.calendarList().list(minAccessRole="owner").execute()
    return [
        {"id": item["id"], "name": item["summary"]}
        for item in result.get("items", [])
    ]
```

**Step 4: Run all google_cal tests**

Run: `pytest tests/test_google_cal.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add calsync/google_cal.py tests/test_google_cal.py
git commit -m "feat: add list_owned_calendars function"
```

---

### Task 6: Add resolve_calendar_by_name function

**Files:**
- Modify: `calsync/google_cal.py`
- Test: `tests/test_google_cal.py`

**Step 1: Write the failing tests**

Add to `tests/test_google_cal.py`:

```python
from calsync.google_cal import resolve_calendar_by_name


def test_resolve_calendar_by_name_unique():
    calendars = [
        {"id": "primary@gmail.com", "name": "Primary"},
        {"id": "work@group.calendar.google.com", "name": "Work"},
    ]
    assert resolve_calendar_by_name("Work", calendars) == "work@group.calendar.google.com"


def test_resolve_calendar_by_name_no_match():
    calendars = [
        {"id": "primary@gmail.com", "name": "Primary"},
    ]
    import pytest
    with pytest.raises(ValueError, match="No calendar found"):
        resolve_calendar_by_name("Work", calendars)


def test_resolve_calendar_by_name_duplicates(monkeypatch):
    calendars = [
        {"id": "work1@group.calendar.google.com", "name": "Work"},
        {"id": "work2@group.calendar.google.com", "name": "Work"},
    ]
    monkeypatch.setattr("builtins.input", lambda _: "2")
    result = resolve_calendar_by_name("Work", calendars)
    assert result == "work2@group.calendar.google.com"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_google_cal.py::test_resolve_calendar_by_name_unique tests/test_google_cal.py::test_resolve_calendar_by_name_no_match tests/test_google_cal.py::test_resolve_calendar_by_name_duplicates -v`
Expected: FAIL — function doesn't exist

**Step 3: Write minimal implementation**

Add to `calsync/google_cal.py`:

```python
def resolve_calendar_by_name(name: str, calendars: list[dict]) -> str:
    matches = [c for c in calendars if c["name"] == name]
    if not matches:
        available = ", ".join(c["name"] for c in calendars)
        raise ValueError(f"No calendar found named '{name}'. Available: {available}")
    if len(matches) == 1:
        return matches[0]["id"]
    # Duplicate names — ask user to pick
    print(f"\nMultiple calendars named '{name}':")
    for i, cal in enumerate(matches, 1):
        print(f"  {i}. {cal['name']} ({cal['id']})")
    pick = int(input("Pick a number: ").strip()) - 1
    return matches[pick]["id"]
```

**Step 4: Run all google_cal tests**

Run: `pytest tests/test_google_cal.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add calsync/google_cal.py tests/test_google_cal.py
git commit -m "feat: add resolve_calendar_by_name with duplicate disambiguation"
```

---

### Task 7: Add state metadata tracking

**Files:**
- Modify: `calsync/state.py`
- Test: `tests/test_state.py`

**Step 1: Write the failing tests**

Add to `tests/test_state.py`:

```python
def test_metadata_default_empty(tmp_path):
    state = SyncState(tmp_path / "state.json")
    assert state.metadata == {}


def test_set_metadata_and_save(tmp_path):
    state_file = tmp_path / "state.json"
    state = SyncState(state_file)
    state.set_metadata("target_calendar_id", "work@gmail.com")
    state.set_metadata("busy_only", True)
    state.save()

    reloaded = SyncState(state_file)
    assert reloaded.metadata["target_calendar_id"] == "work@gmail.com"
    assert reloaded.metadata["busy_only"] is True


def test_metadata_preserved_with_entries(tmp_path):
    state_file = tmp_path / "state.json"
    state = SyncState(state_file)
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00", "2026-03-01T11:00:00", False)
    state.set_metadata("target_calendar_id", "work@gmail.com")
    state.save()

    reloaded = SyncState(state_file)
    assert "uid-1" in reloaded.entries
    assert reloaded.metadata["target_calendar_id"] == "work@gmail.com"


def test_clear_entries_preserves_nothing(tmp_path):
    state_file = tmp_path / "state.json"
    state = SyncState(state_file)
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00", "2026-03-01T11:00:00", False)
    state.set_metadata("target_calendar_id", "work@gmail.com")
    state.save()

    state.clear()
    state.save()

    reloaded = SyncState(state_file)
    assert reloaded.entries == {}
    assert reloaded.metadata == {}
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_state.py::test_metadata_default_empty tests/test_state.py::test_set_metadata_and_save tests/test_state.py::test_metadata_preserved_with_entries tests/test_state.py::test_clear_entries_preserves_nothing -v`
Expected: FAIL — SyncState has no `metadata` or `set_metadata` or `clear`

**Step 3: Write minimal implementation**

Update `calsync/state.py`:

```python
import json
from pathlib import Path


class SyncState:
    def __init__(self, path: Path):
        self.path = path
        self.entries: dict[str, dict] = {}
        self.metadata: dict[str, object] = {}
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, dict) and "_metadata" in data:
                self.metadata = data.pop("_metadata")
            if isinstance(data, dict):
                self.entries = data

    def set(self, icloud_uid: str, google_event_id: str, start: str, end: str, all_day: bool):
        self.entries[icloud_uid] = {
            "google_event_id": google_event_id,
            "start": start,
            "end": end,
            "all_day": all_day,
        }

    def remove(self, icloud_uid: str):
        self.entries.pop(icloud_uid, None)

    def set_metadata(self, key: str, value):
        self.metadata[key] = value

    def clear(self):
        self.entries.clear()
        self.metadata.clear()

    def save(self):
        data = dict(self.entries)
        if self.metadata:
            data["_metadata"] = self.metadata
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)
```

**Step 4: Run all state tests**

Run: `pytest tests/test_state.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add calsync/state.py tests/test_state.py
git commit -m "feat: add metadata tracking to SyncState"
```

---

### Task 8: Update sync engine for busy_only and switch detection

**Files:**
- Modify: `calsync/sync.py`
- Test: `tests/test_sync.py`

**Step 1: Write the failing tests**

Add to `tests/test_sync.py`:

```python
def test_sync_passes_busy_only_to_gcal(tmp_path):
    state = SyncState(tmp_path / "state.json")
    gcal = MagicMock()
    gcal.create_event.return_value = "gid-new"

    events = [Event(uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T11:00:00+00:00",
                    all_day=False, title="Meeting")]

    run_sync(events, state, gcal, busy_only=False, calendar_id="work@gmail.com")

    gcal.create_event.assert_called_once()
    _, kwargs = gcal.create_event.call_args
    assert kwargs["busy_only"] is False


def test_sync_mode_switch_forces_update(tmp_path):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00+00:00", "2026-03-01T11:00:00+00:00", False)
    state.set_metadata("busy_only", True)
    state.save()

    gcal = MagicMock()
    events = [Event(uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T11:00:00+00:00",
                    all_day=False, title="Meeting")]

    # Switch from busy_only=True to False — should force update all events
    run_sync(events, state, gcal, busy_only=False, calendar_id="work@gmail.com")

    gcal.update_event.assert_called_once()


def test_sync_saves_metadata(tmp_path):
    state = SyncState(tmp_path / "state.json")
    gcal = MagicMock()
    gcal.create_event.return_value = "gid-new"

    events = [Event(uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T11:00:00+00:00", all_day=False)]

    run_sync(events, state, gcal, busy_only=False, calendar_id="cal123")

    reloaded = SyncState(tmp_path / "state.json")
    assert reloaded.metadata["busy_only"] is False
    assert reloaded.metadata["target_calendar_id"] == "cal123"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sync.py::test_sync_passes_busy_only_to_gcal tests/test_sync.py::test_sync_mode_switch_forces_update tests/test_sync.py::test_sync_saves_metadata -v`
Expected: FAIL — `run_sync` doesn't accept `busy_only` or `calendar_id`

**Step 3: Write minimal implementation**

Update `calsync/sync.py`:

```python
import logging

from calsync.diff import Event, compute_diff
from calsync.google_cal import GoogleCalClient
from calsync.state import SyncState

logger = logging.getLogger(__name__)


def run_sync(
    events: list[Event],
    state: SyncState,
    gcal: GoogleCalClient,
    busy_only: bool = True,
    calendar_id: str = "",
):
    # Detect mode switch — force update all existing events
    force_update_all = False
    prev_busy_only = state.metadata.get("busy_only")
    if prev_busy_only is not None and prev_busy_only != busy_only:
        logger.info("busy_only changed from %s to %s — forcing update of all events", prev_busy_only, busy_only)
        force_update_all = True

    to_create, to_update, to_delete = compute_diff(events, state.entries)

    # If mode switched, add all unchanged events to the update list
    if force_update_all:
        already_updating = {e.uid for e, _ in to_update}
        creating = {e.uid for e in to_create}
        for event in events:
            if event.uid not in already_updating and event.uid not in creating and event.uid in state.entries:
                to_update.append((event, state.entries[event.uid]["google_event_id"]))

    logger.info("Sync: %d create, %d update, %d delete", len(to_create), len(to_update), len(to_delete))

    for event in to_create:
        google_id = gcal.create_event(event, busy_only=busy_only)
        state.set(event.uid, google_id, event.start, event.end, event.all_day)
        state.save()

    for event, google_id in to_update:
        gcal.update_event(google_id, event, busy_only=busy_only)
        state.set(event.uid, google_id, event.start, event.end, event.all_day)
        state.save()

    for icloud_uid, google_id in to_delete:
        gcal.delete_event(google_id)
        state.remove(icloud_uid)
        state.save()

    # Save metadata
    state.set_metadata("busy_only", busy_only)
    if calendar_id:
        state.set_metadata("target_calendar_id", calendar_id)
    state.save()
```

**Step 4: Update existing sync tests to use new API**

Update the 3 existing tests in `tests/test_sync.py` to pass `busy_only` and `calendar_id` kwargs, and change mock method names from `create_busy_block`/`update_busy_block`/`delete_busy_block` to `create_event`/`update_event`/`delete_event`:

```python
def test_sync_creates_new_events(tmp_path):
    state = SyncState(tmp_path / "state.json")
    gcal = MagicMock()
    gcal.create_event.return_value = "gid-new"

    events = [Event(uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T11:00:00+00:00", all_day=False)]

    run_sync(events, state, gcal, busy_only=True, calendar_id="work@gmail.com")

    gcal.create_event.assert_called_once()
    state_reloaded = SyncState(tmp_path / "state.json")
    assert "uid-1" in state_reloaded.entries


def test_sync_updates_changed_events(tmp_path):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00+00:00", "2026-03-01T11:00:00+00:00", False)
    state.save()

    gcal = MagicMock()
    events = [Event(uid="uid-1", start="2026-03-01T10:00:00+00:00", end="2026-03-01T12:00:00+00:00", all_day=False)]

    run_sync(events, state, gcal, busy_only=True, calendar_id="work@gmail.com")

    gcal.update_event.assert_called_once()


def test_sync_deletes_removed_events(tmp_path):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00+00:00", "2026-03-01T11:00:00+00:00", False)
    state.save()

    gcal = MagicMock()
    events = []

    run_sync(events, state, gcal, busy_only=True, calendar_id="work@gmail.com")

    gcal.delete_event.assert_called_once_with("gid-1")
    state_reloaded = SyncState(tmp_path / "state.json")
    assert "uid-1" not in state_reloaded.entries
```

**Step 5: Run all sync tests**

Run: `pytest tests/test_sync.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add calsync/sync.py tests/test_sync.py
git commit -m "feat: add busy_only and calendar switch detection to sync engine"
```

---

### Task 9: Add calendar switch handling and purge

**Files:**
- Modify: `calsync/sync.py`
- Test: `tests/test_sync.py`

**Step 1: Write the failing tests**

Add to `tests/test_sync.py`:

```python
from calsync.sync import handle_calendar_switch, purge_events


def test_handle_calendar_switch_deletes_old(tmp_path, monkeypatch):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00", "2026-03-01T11:00:00", False)
    state.set("uid-2", "gid-2", "2026-03-02T10:00:00", "2026-03-02T11:00:00", False)
    state.set_metadata("target_calendar_id", "old@gmail.com")
    state.save()

    old_gcal = MagicMock()
    monkeypatch.setattr("builtins.input", lambda _: "y")

    switched = handle_calendar_switch(state, "new@gmail.com", old_gcal)

    assert switched is True
    assert old_gcal.delete_event.call_count == 2
    assert state.entries == {}


def test_handle_calendar_switch_keep_old(tmp_path, monkeypatch):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00", "2026-03-01T11:00:00", False)
    state.set_metadata("target_calendar_id", "old@gmail.com")
    state.save()

    old_gcal = MagicMock()
    monkeypatch.setattr("builtins.input", lambda _: "n")

    switched = handle_calendar_switch(state, "new@gmail.com", old_gcal)

    assert switched is True
    old_gcal.delete_event.assert_not_called()
    assert state.entries == {}


def test_handle_calendar_switch_no_switch(tmp_path):
    state = SyncState(tmp_path / "state.json")
    state.set_metadata("target_calendar_id", "same@gmail.com")
    state.save()

    gcal = MagicMock()
    switched = handle_calendar_switch(state, "same@gmail.com", gcal)

    assert switched is False


def test_handle_calendar_switch_first_run(tmp_path):
    state = SyncState(tmp_path / "state.json")
    gcal = MagicMock()

    switched = handle_calendar_switch(state, "work@gmail.com", gcal)

    assert switched is False


def test_purge_events(tmp_path, monkeypatch):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00", "2026-03-01T11:00:00", False)
    state.set("uid-2", "gid-2", "2026-03-02T10:00:00", "2026-03-02T11:00:00", False)
    state.set_metadata("target_calendar_id", "work@gmail.com")
    state.save()

    gcal = MagicMock()
    monkeypatch.setattr("builtins.input", lambda _: "y")

    purge_events(state, gcal)

    assert gcal.delete_event.call_count == 2
    reloaded = SyncState(tmp_path / "state.json")
    assert reloaded.entries == {}
    assert reloaded.metadata == {}


def test_purge_events_cancel(tmp_path, monkeypatch):
    state = SyncState(tmp_path / "state.json")
    state.set("uid-1", "gid-1", "2026-03-01T10:00:00", "2026-03-01T11:00:00", False)
    state.save()

    gcal = MagicMock()
    monkeypatch.setattr("builtins.input", lambda _: "n")

    purge_events(state, gcal)

    gcal.delete_event.assert_not_called()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sync.py::test_handle_calendar_switch_deletes_old tests/test_sync.py::test_purge_events -v`
Expected: FAIL — functions don't exist

**Step 3: Write minimal implementation**

Add to `calsync/sync.py`:

```python
def handle_calendar_switch(state: SyncState, new_calendar_id: str, gcal: GoogleCalClient) -> bool:
    old_calendar_id = state.metadata.get("target_calendar_id")
    if not old_calendar_id or old_calendar_id == new_calendar_id:
        return False

    logger.info("Calendar switch detected: %s -> %s", old_calendar_id, new_calendar_id)
    answer = input(
        f"Events are currently synced to {old_calendar_id}. "
        f"Delete them before syncing to {new_calendar_id}? (y/n): "
    ).strip().lower()

    if answer in ("y", "yes"):
        for uid, entry in list(state.entries.items()):
            gcal.delete_event(entry["google_event_id"])
            logger.info("Deleted %s from old calendar", uid)

    state.clear()
    state.save()
    return True


def purge_events(state: SyncState, gcal: GoogleCalClient):
    if not state.entries:
        print("No synced events to purge.")
        return

    count = len(state.entries)
    answer = input(f"Delete all {count} synced events and clear state? (y/n): ").strip().lower()
    if answer not in ("y", "yes"):
        print("Cancelled.")
        return

    for uid, entry in list(state.entries.items()):
        gcal.delete_event(entry["google_event_id"])
        logger.info("Purged %s", uid)

    state.clear()
    state.save()
    print(f"Purged {count} events and cleared state.")
```

**Step 4: Run all sync tests**

Run: `pytest tests/test_sync.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add calsync/sync.py tests/test_sync.py
git commit -m "feat: add calendar switch handling and purge command"
```

---

### Task 10: Update CLI with new flags

**Files:**
- Modify: `calsync/cli.py`

**Step 1: Update argparse and main function**

```python
# calsync/cli.py
import argparse
import logging
import sys
from pathlib import Path

from calsync.config import load_config
from calsync.google_cal import (
    GoogleCalClient, authenticate, build_service,
    list_owned_calendars, resolve_calendar_by_name,
)
from calsync.icloud import fetch_icloud_events
from calsync.state import SyncState
from calsync.sync import run_sync, handle_calendar_switch, purge_events

LOG_DIR = Path.home() / ".local" / "log"
LOG_FILE = LOG_DIR / "calsync.log"


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
    parser = argparse.ArgumentParser(description="Sync iCloud calendars to Google Calendar")
    config_dir = Path.home() / ".config" / "calsync"
    parser.add_argument("--config", type=Path, default=config_dir / "config.yaml", help="Path to config file")
    parser.add_argument("--state", type=Path, default=config_dir / "state.json", help="Path to state file")
    parser.add_argument("--auth", action="store_true", help="Run OAuth flow and exit")
    parser.add_argument("--setup", action="store_true", help="Interactive setup wizard")
    parser.add_argument("--calendar", type=str, help="Override target Google Calendar by name")
    parser.add_argument("--busy-only", action="store_true", help="Sync as opaque busy blocks only")
    parser.add_argument("--purge", action="store_true", help="Delete all synced events and clear state")
    args = parser.parse_args()

    if args.setup:
        from calsync.setup import run_setup
        run_setup()
        return

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

        # Resolve calendar ID
        calendar_id = config.google_calendar_id
        if args.calendar:
            calendars = list_owned_calendars(service)
            calendar_id = resolve_calendar_by_name(args.calendar, calendars)
            logger.info("Resolved calendar '%s' to ID: %s", args.calendar, calendar_id)

        gcal = GoogleCalClient(service=service, calendar_id=calendar_id)
        state = SyncState(args.state)

        # Handle purge
        if args.purge:
            purge_events(state, gcal)
            return

        # Handle calendar switch
        handle_calendar_switch(state, calendar_id, gcal)

        # Determine busy_only — CLI flag overrides config
        busy_only = args.busy_only or config.busy_only

        events = fetch_icloud_events(
            username=config.icloud_username,
            app_password=config.icloud_app_password,
            calendar_names=config.icloud_calendars,
            lookahead_days=config.lookahead_days,
        )
        logger.info("Fetched %d events from iCloud", len(events))

        run_sync(events, state, gcal, busy_only=busy_only, calendar_id=calendar_id)
        logger.info("Sync complete")
    except Exception:
        logger.exception("Sync failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Step 2: Run all tests to verify nothing is broken**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add calsync/cli.py
git commit -m "feat: add --calendar, --busy-only, and --purge CLI flags"
```

---

### Task 11: Update setup wizard with calendar picker

**Files:**
- Modify: `calsync/setup.py`

**Step 1: Update the setup wizard**

Replace the Google Calendar text prompt (lines 79-80) with a calendar picker. Add busy_only prompt. The setup flow becomes:

```python
    # Step 3: Google OAuth credentials (moved before calendar selection)
    credentials_file = CONFIG_DIR / "credentials.json"
    if not credentials_file.exists():
        print(f"\nGoogle OAuth credentials file not found at: {credentials_file}")
        print("To get it:")
        print("  1. Go to https://console.cloud.google.com")
        print("  2. Create a project (or use existing)")
        print("  3. Enable the Google Calendar API")
        print("  4. Go to Credentials > Create Credentials > OAuth client ID > Desktop app")
        print(f"  5. Download the JSON and save it as: {credentials_file}")
        input("\nPress Enter when credentials.json is in place...")
        if not credentials_file.exists():
            print("credentials.json still not found. Exiting.")
            sys.exit(1)

    # Step 4: Google OAuth
    print("\nStep 3: Google OAuth")
    print("A browser window will open for Google authorization...")
    try:
        creds = authenticate(credentials_file, CONFIG_DIR / "token.json")
        print("Google authentication complete.")
    except Exception as e:
        print(f"Google auth failed: {e}")
        sys.exit(1)

    # Step 5: Pick Google Calendar
    from calsync.google_cal import build_service, list_owned_calendars
    service = build_service(creds)
    owned_calendars = list_owned_calendars(service)

    if not owned_calendars:
        print("No owned calendars found on this Google account.")
        sys.exit(1)

    print("\nStep 4: Choose target Google Calendar")
    print("\nYour Google calendars:")
    for i, cal in enumerate(owned_calendars, 1):
        print(f"  {i}. {cal['name']}")
    print()
    pick = int(input("Which calendar to sync to? (number): ").strip()) - 1
    calendar_id = owned_calendars[pick]["id"]
    print(f"Selected: {owned_calendars[pick]['name']} ({calendar_id})")

    # Step 6: Busy only?
    print("\nStep 5: Event detail level")
    answer = _prompt("Sync full event details (title, location, description)?", "y")
    busy_only = answer.lower() not in ("y", "yes")
```

Then update the config dict to include `busy_only`:

```python
    config = {
        "icloud": {
            "username": username,
            "app_password": app_password,
            "calendars": selected,
        },
        "google": {
            "calendar_id": calendar_id,
            "credentials_file": "credentials.json",
            "token_file": "token.json",
        },
        "sync": {
            "lookahead_days": 30,
            "busy_only": busy_only,
        },
    }
```

**Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add calsync/setup.py
git commit -m "feat: setup wizard lists owned Google calendars and asks busy_only preference"
```

---

### Task 12: Remove old method aliases, final cleanup

**Files:**
- Modify: `calsync/google_cal.py`
- Test: all test files

**Step 1: Remove aliases from GoogleCalClient**

Delete these lines from `calsync/google_cal.py`:

```python
    create_busy_block = create_event
    update_busy_block = update_event
    delete_busy_block = delete_event
```

**Step 2: Search for any remaining references to old method names**

Run: `grep -r "busy_block" calsync/ tests/`

Update any remaining references to use the new names.

**Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: remove deprecated busy_block method aliases"
```

---

### Task 13: Run full test suite and verify

**Step 1: Run the complete test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 2: Verify the CLI help text**

Run: `python -m calsync.cli --help`
Expected: Shows `--calendar`, `--busy-only`, and `--purge` flags in help output.
