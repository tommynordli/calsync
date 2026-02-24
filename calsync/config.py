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
    busy_only: bool


def load_config(path: Path) -> Config:
    with open(path) as f:
        raw = yaml.safe_load(f)

    icloud = raw["icloud"]
    google = raw["google"]
    sync = raw.get("sync", {})

    config_dir = path.parent

    def _resolve(p: str) -> Path:
        """Resolve relative paths against the config file's directory."""
        fp = Path(p)
        return fp if fp.is_absolute() else config_dir / fp

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
