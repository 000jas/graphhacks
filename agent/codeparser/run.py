#!/usr/bin/env python3
"""GraphAgent Standalone 1-Command Cross-Platform Runner.

Runs on any Mac, Linux, or Windows machine without prior installation.
Usage:
    python3 run.py .
    python3 run.py /path/to/repo --verbose
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    script_dir = Path(__file__).resolve().parent
    cache_dir = Path.home() / ".cache" / "graphagent"
    venv_dir = cache_dir / "venv"

    # Identify venv python executable
    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
        venv_graphagent = venv_dir / "Scripts" / "graphagent.exe"
    else:
        venv_python = venv_dir / "bin" / "python3"
        venv_graphagent = venv_dir / "bin" / "graphagent"

    # Bootstrap or repair isolated environment if needed
    needs_install = not venv_graphagent.exists()
    if not needs_install:
        # Check if import works in case repository directory was moved or renamed
        test_import = subprocess.call(
            [str(venv_python), "-c", "import graphagent"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if test_import != 0:
            needs_install = True

    if needs_install:
        print("⚡ Synchronizing environment in ~/.cache/graphagent...")
        cache_dir.mkdir(parents=True, exist_ok=True)
        if not (venv_dir / "bin" / "python3").exists() and not (venv_dir / "Scripts" / "python.exe").exists():
            subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
            subprocess.check_call([str(venv_python), "-m", "pip", "install", "--upgrade", "--quiet", "pip"])
        subprocess.check_call([str(venv_python), "-m", "pip", "install", "--quiet", "falkordb", "python-dotenv", "-e", str(script_dir)])
        print("✅ Environment ready!")

    # Forward arguments to graphagent
    args = sys.argv[1:]

    # Help flag
    if args and args[0] in ("-h", "--help", "help"):
        print("""
GraphAgent 2-Step Workflow:
===========================
  Step 1: Parse code and generate output.json
      python3 run.py .
      python3 run.py /path/to/repo

  Step 2: Save output.json into FalkorDB
      python3 run.py save-db
      python3 run.py save-db output.json --graph graphos_dev
""")
        cmd = [str(venv_graphagent), "--help"]
        sys.exit(subprocess.call(cmd))

    # Check if subcommand is save-db / ingest
    if args and args[0] in ("save-db", "ingest", "save_to_db", "save"):
        cmd = [str(venv_graphagent), "save-db"] + args[1:]
    elif args and args[0] == "parse":
        cmd = [str(venv_graphagent), "parse"] + args[1:]
    else:
        # Default command: parse target path (defaults to '.')
        target_path = args[0] if args else "."
        remaining_flags = args[1:] if len(args) > 1 else []
        cmd = [str(venv_graphagent), "parse", target_path] + remaining_flags

    exit_code = subprocess.call(cmd)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
