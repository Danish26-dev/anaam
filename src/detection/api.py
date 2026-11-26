"""Stable integration facade for Danish's detection and identity-evidence modules.

Omkar's pipeline and writers import only this module. It now delegates to the real
DetectionEngine (src/detection/engine.py): the temporary regex stub in stub_detector.py
is no longer on the call path for main.py, but stays in the repo so the unit tests that
exercise the facade in isolation (without building a full FileEnvelope set) still have a
lightweight implementation to fall back on if ever imported directly.

Call order contract (see DetectionEngine.prepare docstring): `prepare_detection_engine`
must run once, after every input file has been ingested into a FileEnvelope and before
the first `extract_identity_evidence` or `resolve_spans` call. main.py's two-pass
ingestion loop exists specifically to satisfy this.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Same dual-layout problem src/contracts.py solves, and for the same reason: main.py
# puts `src/` itself on sys.path (so `core.interfaces` resolves as a top-level package),
# while Danish's tests put the repo ROOT on sys.path and reach this module as
# `src.detection.api`. Engine.py and its siblings use `from .. import contracts as c`,
# a true relative import that only works when this package's parent is the real `src`
# package -- which requires the repo root (this file's grandparent) to also be
# reachable so `import src` succeeds before any relative import inside engine.py runs.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.interfaces import FileEnvelope, IdentityEvidence, RecordEnvelope, ResolvedSpan, KEEP
from .engine import DetectionEngine, apply_placeholders

_engine = DetectionEngine()
_prepared = False


def detection_engine() -> DetectionEngine:
    """The single shared engine instance, for callers (the release verifier) that need
    the real DetectionEngine object itself rather than just these wrapper functions.
    """
    return _engine


def prepare_detection_engine(files: list[FileEnvelope]) -> None:
    """Run the engine's cross-file indexing pass. Must be called exactly once, after all
    FileEnvelopes for this run are built and before any detection/evidence call below.
    """
    global _prepared
    _engine.prepare(files)
    _prepared = True


def resolve_spans(text: str) -> list[ResolvedSpan]:
    return _engine.detect_text(text)


def apply_spans(text: str, spans: list[ResolvedSpan]) -> tuple[str, int]:
    count = sum(1 for s in spans if s.action != KEEP)
    return apply_placeholders(text, spans), count


def extract_identity_evidence(
    record: RecordEnvelope,
    file_envelope: FileEnvelope,
    fallback_text: str | None = None,
) -> IdentityEvidence:
    """Return raw in-memory evidence for one envelope.

    `fallback_text` is accepted for backward compatibility with call sites written
    against the old stub-only signature, but the real engine classifies
    `record.fields`/`record.free_text` directly from `file_envelope` and ignores it.
    """
    detection = _engine.detect_record(record, file_envelope)
    return detection.evidence
