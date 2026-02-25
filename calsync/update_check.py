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
