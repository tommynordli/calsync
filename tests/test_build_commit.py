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
