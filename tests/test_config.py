from pathlib import Path
from calsync.config import load_config


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
    assert config.google_credentials_file == tmp_path / "creds.json"
    assert config.google_token_file == tmp_path / "tok.json"
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


def test_load_config_with_reverse_sync(tmp_path):
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
reverse_sync:
  enabled: true
  google_calendar: "Work"
  icloud_calendar: "Work Events"
  busy_only: true
""")
    config = load_config(config_file)
    assert config.reverse_sync is not None
    assert config.reverse_sync.enabled is True
    assert config.reverse_sync.google_calendar == "Work"
    assert config.reverse_sync.icloud_calendar == "Work Events"
    assert config.reverse_sync.busy_only is True


def test_load_config_without_reverse_sync(tmp_path):
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
    assert config.reverse_sync is None


def test_load_config_reverse_sync_disabled(tmp_path):
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
reverse_sync:
  enabled: false
  google_calendar: "Work"
  icloud_calendar: "Work Events"
""")
    config = load_config(config_file)
    assert config.reverse_sync is not None
    assert config.reverse_sync.enabled is False


def test_load_config_missing_file():
    import pytest
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/config.yaml"))
