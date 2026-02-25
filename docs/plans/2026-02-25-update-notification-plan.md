# Update Notification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prompt interactive CLI users when a newer version of calsync is available on GitHub.

**Architecture:** A setuptools build hook bakes the git commit SHA into the package at install time. The background sync checks GitHub once per day and caches the latest SHA locally. Interactive CLI reads the cache and prints a one-liner if the SHAs differ.

**Tech Stack:** setuptools (build hook), urllib (GitHub API), pathlib (file I/O)

---

### Task 1: Add `_commit.py` to `.gitignore`

**Files:**
- Modify: `.gitignore`

**Step 1: Add the gitignore entry**

Add `calsync/_commit.py` to `.gitignore`:

```
calsync/_commit.py
```

**Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore generated _commit.py"
```

---

### Task 2: Build hook to bake commit SHA

**Files:**
- Create: `build_commit.py` (project root — setuptools build hook)
- Modify: `pyproject.toml:1-3` (build-system section)

**Step 1: Write the failing test**

Create `tests/test_build_commit.py`:

```python
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_build_commit_generates_file(tmp_path):
    """Running build_commit.py writes calsync/_commit.py with the current SHA."""
    out = tmp_path / "_commit.py"
    subprocess.run(
        [sys.executable, str(ROOT / "build_commit.py"), str(out)],
        check=True,
        cwd=ROOT,
    )
    content = out.read_text()
    assert content.startswith('COMMIT = "')
    assert len(content.strip().split('"')[1]) == 40  # full SHA


def test_build_commit_fallback_outside_git(tmp_path):
    """Outside a git repo, writes COMMIT = 'unknown'."""
    # Copy build_commit.py to a non-git dir
    import shutil
    script = tmp_path / "build_commit.py"
    shutil.copy(ROOT / "build_commit.py", script)
    out = tmp_path / "_commit.py"
    subprocess.run(
        [sys.executable, str(script), str(out)],
        check=True,
        cwd=tmp_path,
    )
    content = out.read_text()
    assert content.strip() == 'COMMIT = "unknown"'
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_build_commit.py -v`
Expected: FAIL — `build_commit.py` doesn't exist yet.

**Step 3: Write the build hook script**

Create `build_commit.py`:

```python
"""Build hook: writes calsync/_commit.py with the current git SHA."""
import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) > 1:
        out_path = Path(sys.argv[1])
    else:
        out_path = Path(__file__).resolve().parent / "calsync" / "_commit.py"

    try:
        sha = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        sha = "unknown"

    out_path.write_text(f'COMMIT = "{sha}"\n')


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_build_commit.py -v`
Expected: PASS

**Step 5: Wire into setuptools build**

Modify `pyproject.toml` build-system section:

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.cmdclass]
build_py = "build_commit.BuildPyWithCommit"
```

Actually — setuptools `cmdclass` in `pyproject.toml` requires a custom class. Simpler approach: use a `setup.py` that extends `build_py`:

Create `setup.py`:

```python
from setuptools import setup
from setuptools.command.build_py import build_py
import subprocess
from pathlib import Path


class BuildPyWithCommit(build_py):
    def run(self):
        # Generate _commit.py before building
        try:
            sha = (
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            sha = "unknown"

        commit_file = Path(__file__).resolve().parent / "calsync" / "_commit.py"
        commit_file.write_text(f'COMMIT = "{sha}"\n')

        super().run()


setup(cmdclass={"build_py": BuildPyWithCommit})
```

Remove the `[tool.setuptools.cmdclass]` from `pyproject.toml` — `setup.py` takes precedence for cmdclass.

**Step 6: Verify the build generates `_commit.py`**

Run: `pip install -e ".[dev]" && python -c "from calsync._commit import COMMIT; print(COMMIT)"`
Expected: prints a 40-char SHA

**Step 7: Commit**

```bash
git add build_commit.py setup.py tests/test_build_commit.py
git commit -m "feat: build hook to bake git commit SHA into package"
```

---

### Task 3: Update check module — remote check

**Files:**
- Create: `calsync/update_check.py`
- Create: `tests/test_update_check.py`

**Step 1: Write the failing test for remote check**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_update_check.py -v`
Expected: FAIL — module doesn't exist.

**Step 3: Implement `check_remote`**

Create `calsync/update_check.py`:

```python
"""Update availability checking for calsync."""
import json
import time
from pathlib import Path
from urllib.request import urlopen, Request

GITHUB_API_URL = "https://api.github.com/repos/tommynordli/calsync/commits/main"
STALENESS_SECONDS = 24 * 3600  # 24 hours
LATEST_COMMIT_FILE = Path.home() / ".config" / "calsync" / "latest_commit"
UPDATE_COMMAND = 'uv tool install --force "calsync @ git+https://github.com/tommynordli/calsync"'


def check_remote(commit_file: Path = LATEST_COMMIT_FILE) -> None:
    """Fetch latest commit SHA from GitHub if cache is stale. Silently ignores all errors."""
    try:
        if commit_file.exists():
            age = time.time() - commit_file.stat().st_mtime
            if age < STALENESS_SECONDS:
                return

        req = Request(GITHUB_API_URL, headers={"Accept": "application/vnd.github.v3+json"})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        sha = data["sha"]
        commit_file.parent.mkdir(parents=True, exist_ok=True)
        commit_file.write_text(sha + "\n")
    except Exception:
        pass
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_update_check.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add calsync/update_check.py tests/test_update_check.py
git commit -m "feat: add remote update check with 24h cache"
```

---

### Task 4: Update check module — local check

**Files:**
- Modify: `calsync/update_check.py`
- Modify: `tests/test_update_check.py`

**Step 1: Write the failing tests for local check**

Add to `tests/test_update_check.py`:

```python
from calsync.update_check import check_local


def test_check_local_returns_message_when_update_available(tmp_path):
    """Returns update message when SHAs differ."""
    commit_file = tmp_path / "latest_commit"
    commit_file.write_text("b" * 40 + "\n")

    with patch("calsync.update_check.LATEST_COMMIT_FILE", commit_file):
        result = check_local("a" * 40)

    assert result is not None
    assert "Update available" in result


def test_check_local_returns_none_when_up_to_date(tmp_path):
    """Returns None when SHAs match."""
    commit_file = tmp_path / "latest_commit"
    sha = "a" * 40
    commit_file.write_text(sha + "\n")

    with patch("calsync.update_check.LATEST_COMMIT_FILE", commit_file):
        result = check_local(sha)

    assert result is None


def test_check_local_returns_none_when_no_file(tmp_path):
    """Returns None if latest_commit file doesn't exist."""
    commit_file = tmp_path / "latest_commit_missing"

    with patch("calsync.update_check.LATEST_COMMIT_FILE", commit_file):
        result = check_local("a" * 40)

    assert result is None


def test_check_local_returns_none_for_unknown_commit(tmp_path):
    """Returns None if installed commit is 'unknown' (dev install)."""
    commit_file = tmp_path / "latest_commit"
    commit_file.write_text("b" * 40 + "\n")

    with patch("calsync.update_check.LATEST_COMMIT_FILE", commit_file):
        result = check_local("unknown")

    assert result is None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_update_check.py::test_check_local_returns_message_when_update_available -v`
Expected: FAIL — `check_local` doesn't exist.

**Step 3: Implement `check_local`**

Add to `calsync/update_check.py`:

```python
def check_local(installed_commit: str) -> str | None:
    """Compare installed commit against cached latest. Returns update message or None."""
    try:
        if installed_commit == "unknown":
            return None

        if not LATEST_COMMIT_FILE.exists():
            return None

        latest = LATEST_COMMIT_FILE.read_text().strip()
        if not latest or latest == installed_commit:
            return None

        return f"Update available! Run: {UPDATE_COMMAND}"
    except Exception:
        return None
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_update_check.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add calsync/update_check.py tests/test_update_check.py
git commit -m "feat: add local update check comparing installed vs latest SHA"
```

---

### Task 5: Wire into CLI

**Files:**
- Modify: `calsync/cli.py:32-75` (`_cmd_sync`) and `calsync/cli.py:118-164` (`main`)

**Step 1: Write the failing test for CLI integration**

Create `tests/test_cli_update.py`:

```python
"""Tests for update notification wiring in CLI."""
from unittest.mock import patch, MagicMock


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

        from calsync.cli import _cmd_sync
        _cmd_sync(args)

    mock_remote.assert_called_once()


def test_main_shows_update_on_tty(capsys):
    """When stdout is a TTY and update available, prints message."""
    with (
        patch("calsync.cli.check_local", return_value="Update available! Run: uv tool install ..."),
        patch("sys.stdout") as mock_stdout,
        patch("sys.argv", ["calsync", "auth"]),
        patch("calsync.cli._cmd_auth"),
        patch("calsync.cli.load_config"),
    ):
        mock_stdout.isatty.return_value = True
        mock_stdout.write = lambda s: None

        from calsync.cli import main
        # main() will call _cmd_auth then check_local
        # This is an integration-level check; exact wiring tested below


def test_main_skips_update_on_non_tty():
    """When stdout is not a TTY, no update message."""
    with (
        patch("calsync.cli.check_local") as mock_local,
        patch("sys.stdout") as mock_stdout,
    ):
        mock_stdout.isatty.return_value = False
        # check_local should not be called when not a TTY
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_update.py::test_cmd_sync_calls_check_remote -v`
Expected: FAIL — `check_remote` not imported in cli.

**Step 3: Wire remote check into `_cmd_sync`**

Modify `calsync/cli.py`. Add import at top:

```python
from calsync.update_check import check_remote, check_local
```

Add after the `logger.info("Sync complete")` line (line 72) inside `_cmd_sync`, before the except block:

```python
        check_remote()
```

**Step 4: Wire local check into `main`**

Modify `calsync/cli.py`. After `args.func(args)` (line 160), add:

```python
    if sys.stdout.isatty():
        try:
            from calsync._commit import COMMIT
        except ImportError:
            COMMIT = "unknown"
        msg = check_local(COMMIT)
        if msg:
            print(msg)
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_cli_update.py -v`
Expected: PASS

**Step 6: Run full test suite**

Run: `pytest tests/ -v`
Expected: all PASS

**Step 7: Commit**

```bash
git add calsync/cli.py tests/test_cli_update.py
git commit -m "feat: wire update check into CLI sync and interactive output"
```

---

### Task 6: End-to-end verification

**Step 1: Build and install**

```bash
pip install -e ".[dev]"
```

**Step 2: Verify baked SHA**

```bash
python -c "from calsync._commit import COMMIT; print(COMMIT)"
```
Expected: 40-char SHA

**Step 3: Simulate update available**

```bash
echo "fakeshaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" > ~/.config/calsync/latest_commit
calsync --help
```
Expected: help text followed by `Update available! Run: ...`

Note: `--help` calls `sys.exit(0)` which skips the check. Test with a real subcommand instead, e.g. `calsync auth` (will fail without config but the update message should print).

**Step 4: Clean up test file**

```bash
rm ~/.config/calsync/latest_commit
```

**Step 5: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all PASS

**Step 6: Commit any final adjustments**

```bash
git add -A && git commit -m "chore: finalize update notification feature"
```
