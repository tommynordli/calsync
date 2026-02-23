# calsync/state.py
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
