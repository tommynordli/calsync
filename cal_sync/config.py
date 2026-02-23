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
