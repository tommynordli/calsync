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
