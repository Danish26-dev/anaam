"""Path-safety helpers used during file-tree traversal."""
from __future__ import annotations

from pathlib import Path


def is_subpath(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def is_unsafe_symlink(path: Path, root: Path) -> bool:
    """True if `path` is a symlink whose resolved target escapes `root`."""
    if not path.is_symlink():
        return False
    target = path.resolve(strict=False)
    return not is_subpath(target, root)


def iter_files_sorted(root: Path):
    """Yield every regular file under root, in a stable sorted order.

    Sorting by the POSIX-style relative path string (not OS path objects) keeps traversal
    order identical across Windows and Linux, which matters because the evaluator runs on
    Linux while development happens on Windows.
    """
    files = [p for p in root.rglob("*") if p.is_file()]
    files.sort(key=lambda p: p.relative_to(root).as_posix())
    return files
