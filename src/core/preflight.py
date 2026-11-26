"""Preflight checks: validate the invocation before any input byte is read.

Everything here must fail CLOSED and SAFE: raise ConfigError with a reason code, never a
raw path or value, before any processing starts.
"""
from __future__ import annotations

import locale
import os
from pathlib import Path

from .errors import ConfigError
from .keys import KeySet, MissingSecretError, load_keyset


def _resolve_strict(p: Path) -> Path:
    """Resolve a path to its real, absolute form, following symlinks, without raising on
    a nonexistent path (Path.resolve(strict=False) is fine pre-creation for --output).
    """
    return p.resolve(strict=False)


def _is_subpath(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def check_paths(input_dir: str, output_dir: str) -> tuple[Path, Path]:
    """Validate --input/--output. Returns resolved (input, output) paths or raises
    ConfigError with a safe reason code.
    """
    inp = _resolve_strict(Path(input_dir))
    out = _resolve_strict(Path(output_dir))

    if not inp.exists() or not inp.is_dir():
        raise ConfigError("input_missing_or_not_a_directory")

    if inp == out:
        raise ConfigError("input_and_output_identical")

    if _is_subpath(out, inp):
        raise ConfigError("output_inside_input")

    if _is_subpath(inp, out):
        # Input must never be writable through output traversal either.
        raise ConfigError("input_inside_output")

    # Unsafe symlink check: no file *inside* input may resolve outside the input root.
    for entry in inp.rglob("*"):
        if entry.is_symlink():
            target = entry.resolve(strict=False)
            if not _is_subpath(target, inp):
                raise ConfigError("unsafe_symlink_in_input")

    if out.exists():
        if out.is_file():
            raise ConfigError("output_path_is_a_file")
        stale = any(out.iterdir()) if out.is_dir() else False
        if stale:
            raise ConfigError("output_not_empty")
    else:
        out.mkdir(parents=True, exist_ok=True)

    return inp, out


def check_secret(env: dict | None = None) -> KeySet:
    """Require RAKSHA_SECRET and derive the KeySet. Raises ConfigError, never the secret."""
    try:
        return load_keyset(env)
    except MissingSecretError:
        raise ConfigError("raksha_secret_missing") from None


def configure_determinism() -> None:
    """Pin settings that could otherwise make output order- or locale-dependent."""
    os.environ["TZ"] = "UTC"
    try:
        import time as _time

        if hasattr(_time, "tzset"):
            _time.tzset()
    except Exception:  # noqa: BLE001 - tzset is unavailable on some platforms (Windows)
        pass
    try:
        locale.setlocale(locale.LC_ALL, "C")
    except locale.Error:
        pass
    # Hash randomization would not affect our own deterministic HMAC-based ordering, but
    # pin it anyway so any accidental dict/set-order dependency in future code is stable.
    os.environ.setdefault("PYTHONHASHSEED", "0")


def run_preflight(input_dir: str, output_dir: str, env: dict | None = None) -> tuple[Path, Path, KeySet]:
    """Run every preflight check in order. Raises ConfigError on the first failure.

    Secret validation comes first because path validation may create the empty output
    directory. A missing secret must fail without mutating the filesystem.
    """
    keys = check_secret(env)
    inp, out = check_paths(input_dir, output_dir)
    configure_determinism()
    return inp, out, keys
