"""Tests for update notification wiring in CLI."""
from unittest.mock import patch, MagicMock

from calsync.cli import _cmd_sync


def test_cmd_sync_calls_check_remote(tmp_path):
    """After sync completes, check_remote is called."""
    with (
        patch("calsync.cli.load_config") as mock_config,
        patch("calsync.cli.authenticate"),
        patch("calsync.cli.build_service"),
        patch("calsync.cli.fetch_icloud_events", return_value=[]),
        patch("calsync.cli.run_sync"),
        patch("calsync.cli.SyncState") as mock_state_cls,
        patch("calsync.cli.check_remote") as mock_remote,
        patch("calsync.cli._setup_logging"),
    ):
        mock_config.return_value = MagicMock(
            google_credentials_file="creds.json",
            google_token_file="token.json",
            google_calendar_id="cal_id",
            icloud_username="user",
            icloud_app_password="pass",
            icloud_calendars=["Cal"],
            lookahead_days=30,
            busy_only=False,
        )
        mock_state = MagicMock()
        mock_state.metadata = {}
        mock_state_cls.return_value = mock_state

        args = MagicMock()
        args.config = tmp_path / "config.yaml"
        args.state = tmp_path / "state.json"
        args.calendar = None
        args.busy_only = False

        _cmd_sync(args)

    mock_remote.assert_called_once()


def test_main_shows_update_on_tty():
    """When stdout is a TTY and update available, prints update message."""
    with (
        patch("calsync.cli.check_local", return_value="Update available! Run: uv tool install ...") as mock_local,
        patch("sys.argv", ["calsync", "setup"]),
        patch("calsync.cli._cmd_setup"),
        patch("sys.stdout") as mock_stdout,
    ):
        mock_stdout.isatty.return_value = True
        # We need print to work — capture via mock_stdout.write
        written = []
        mock_stdout.write = lambda s: written.append(s)

        from calsync.cli import main
        main()

    mock_local.assert_called_once()
    assert any("Update available" in s for s in written)


def test_main_skips_update_on_non_tty():
    """When stdout is not a TTY, check_local is never called."""
    with (
        patch("calsync.cli.check_local") as mock_local,
        patch("sys.argv", ["calsync", "setup"]),
        patch("calsync.cli._cmd_setup"),
        patch("sys.stdout") as mock_stdout,
    ):
        mock_stdout.isatty.return_value = False

        from calsync.cli import main
        main()

    mock_local.assert_not_called()
