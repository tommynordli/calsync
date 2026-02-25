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
