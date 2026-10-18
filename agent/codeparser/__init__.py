"""Code Parser module inside GraphOS agent.

Provides Tree-sitter multi-language code parsing, relationship resolution,
and direct FalkorDB graph ingestion.
"""

from pathlib import Path
import sys

# Ensure inner src directory is in sys.path
_src_dir = Path(__file__).resolve().parent / "src"
if _src_dir.is_dir() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

try:
    from graphagent import (
        PARSER_VERSION,
        Exporter,
        LanguageRegistry,
        Scanner,
        SymbolExtractor,
        RelationshipResolver,
        GraphData,
        Node,
        Edge,
    )
except ImportError:
    pass
