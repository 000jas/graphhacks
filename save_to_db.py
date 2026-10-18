#!/usr/bin/env python3
"""Save code parser output JSON to FalkorDB.

Usage:
    python3 save_to_db.py
    python3 save_to_db.py output.json
    python3 save_to_db.py output.json --graph graphos_dev
"""

import os
import sys
import subprocess
from pathlib import Path

root_dir = Path(__file__).resolve().parent
codeparser_src = root_dir / "agent" / "codeparser" / "src"
if not codeparser_src.is_dir():
    codeparser_src = root_dir / "codeparser" / "src"

if codeparser_src.is_dir() and str(codeparser_src) not in sys.path:
    sys.path.insert(0, str(codeparser_src))

try:
    import falkordb
    from graphagent.cli import run_save_db
except ImportError:
    # Forward to the standalone self-bootstrapped runner
    runner = root_dir / "agent" / "codeparser" / "run.py"
    if not runner.exists():
        runner = root_dir / "codeparser" / "run.py"
    if runner.exists():
        sys.exit(subprocess.call([sys.executable, str(runner), "save-db"] + sys.argv[1:]))
    raise

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

