# calsync/state.py
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
