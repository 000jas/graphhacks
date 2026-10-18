#!/usr/bin/env python3
"""GraphAgent Code Parser & Ingestion Runner.

Usage:
    # Step 1: Parse a repository to output.json
    python3 run.py .
    python3 run.py /path/to/repo

    # Step 2: Save output.json into FalkorDB
    python3 run.py save-db
    python3 run.py save-db output.json --graph graphos_dev
"""

import sys
import subprocess
from pathlib import Path


def main():
    root_dir = Path(__file__).resolve().parent
    runner = root_dir / "agent" / "codeparser" / "run.py"
    if not runner.exists():
        runner = root_dir / "codeparser" / "run.py"
    if not runner.exists():
        print(f"Error: Could not locate parser runner at {runner}", file=sys.stderr)
        sys.exit(1)

    sys.exit(subprocess.call([sys.executable, str(runner)] + sys.argv[1:]))


if __name__ == "__main__":
    main()
