# tests/test_cli.py
import logging

from calsync.cli import _setup_logging


def test_setup_logging_filters_third_party(tmp_path, monkeypatch):
    monkeypatch.setattr("calsync.cli.LOG_DIR", tmp_path)
    monkeypatch.setattr("calsync.cli.LOG_FILE", tmp_path / "calsync.log")

    # Reset root logger handlers from prior tests
    root = logging.getLogger()
    root.handlers.clear()

    _setup_logging()

    stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)]
    assert len(stream_handlers) == 1
    handler = stream_handlers[0]

    # calsync loggers should pass the filter
    calsync_record = logging.LogRecord("calsync.sync", logging.INFO, "", 0, "test", (), None)
    assert handler.filter(calsync_record)

    # Third-party loggers should be filtered out
    gapi_record = logging.LogRecord("googleapiclient.discovery_cache", logging.INFO, "", 0, "noise", (), None)
    assert not handler.filter(gapi_record)
