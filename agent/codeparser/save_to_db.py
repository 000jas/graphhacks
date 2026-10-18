#!/usr/bin/env python3
"""Standalone runner to save GraphAgent parsed output.json into FalkorDB.

Usage:
    python3 save_to_db.py
    python3 save_to_db.py output.json
    python3 save_to_db.py output.json --graph graphos_dev
"""

import sys
from pathlib import Path

# Add src to sys.path if not installed
src_dir = Path(__file__).resolve().parent / "src"
if src_dir.is_dir() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from graphagent.cli import run_save_db

if __name__ == "__main__":
    args = sys.argv[1:]
    target_file = None
    target_graph = None

    idx = 0
    while idx < len(args):
        arg = args[idx]
        if arg in ("-g", "--graph") and idx + 1 < len(args):
            target_graph = args[idx + 1]
            idx += 2
        elif not arg.startswith("-") and target_file is None:
            target_file = arg
            idx += 1
        else:
            idx += 1

    code = run_save_db(file_path=target_file, graph_name=target_graph, verbose=True)
    sys.exit(code)
