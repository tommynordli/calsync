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
