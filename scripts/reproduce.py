#!/usr/bin/env python3
"""Run the preserved model in a temporary directory; emit its JSON on stdout."""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/self-caused-silence/upstream/self_caused_silence.py"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="self-caused-silence-") as directory:
        script = Path(directory) / SOURCE.name
        shutil.copyfile(SOURCE, script)
        run = subprocess.run(
            [sys.executable, "-B", str(script)],
            cwd=directory,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        sys.stderr.write(run.stdout)
        sys.stderr.write(run.stderr)
        sys.stdout.write(script.with_name("results.json").read_text())
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
