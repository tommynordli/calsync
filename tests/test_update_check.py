# tests/test_update_check.py
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from calsync.update_check import check_remote


def test_check_remote_writes_sha(tmp_path):
    """Fetches latest SHA from GitHub and writes to file."""
    commit_file = tmp_path / "latest_commit"
    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps({"sha": "a" * 40}).encode()
    fake_response.__enter__ = lambda s: s
    fake_response.__exit__ = MagicMock(return_value=False)

    with patch("calsync.update_check.urlopen", return_value=fake_response):
        check_remote(commit_file)

    assert commit_file.read_text().strip() == "a" * 40


def test_check_remote_skips_when_fresh(tmp_path):
    """Skips API call if file was modified less than 24h ago."""
    commit_file = tmp_path / "latest_commit"
    commit_file.write_text("old_sha")

    with patch("calsync.update_check.urlopen") as mock_url:
        check_remote(commit_file)

    mock_url.assert_not_called()


def test_check_remote_checks_when_stale(tmp_path):
    """Makes API call if file is older than 24h."""
    commit_file = tmp_path / "latest_commit"
    commit_file.write_text("old_sha")
    # Backdate mtime by 25 hours
    old_time = time.time() - 25 * 3600
    import os
    os.utime(commit_file, (old_time, old_time))

    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps({"sha": "b" * 40}).encode()
    fake_response.__enter__ = lambda s: s
    fake_response.__exit__ = MagicMock(return_value=False)

    with patch("calsync.update_check.urlopen", return_value=fake_response):
        check_remote(commit_file)

    assert commit_file.read_text().strip() == "b" * 40


def test_check_remote_silently_ignores_errors(tmp_path):
    """Network errors are silently swallowed."""
    commit_file = tmp_path / "latest_commit"

    with patch("calsync.update_check.urlopen", side_effect=Exception("network")):
        check_remote(commit_file)  # should not raise

    assert not commit_file.exists()
