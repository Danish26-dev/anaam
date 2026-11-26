"""Pytest root: puts `src/` on sys.path, the same layout `main.py` uses, so tests import
`core`, `detection`, `verify` and the other packages as top-level packages."""
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
