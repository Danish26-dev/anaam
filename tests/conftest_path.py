"""Adds src/ to sys.path so tests can import package modules directly.

Imported (for its side effect) at the top of every test module instead of relying on a
pytest conftest.py, so the suite also runs under plain `python -m unittest discover`
with the standard library only -- no pytest dependency required.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
