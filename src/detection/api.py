"""Stable integration façade for Danish's detection and identity-evidence modules.

Omkar's pipeline and writers import only this module. During parallel development it
adapts the temporary regex stub. Danish can replace these function bodies with the real
clinical shield, span resolver, multilingual detectors and evidence extractor without
changing ingestion, identity resolution or serialization call sites.
"""
from __future__ import annotations

from core.interfaces import IdentityEvidence, RecordEnvelope, ResolvedSpan
from .stub_detector import (
    apply_resolved_spans as _apply_stub_spans,
    extract_identity_evidence_stub,
    resolve_spans_in_text as _resolve_stub_spans,
)


def resolve_spans(text: str) -> list[ResolvedSpan]:
    return _resolve_stub_spans(text)


def apply_spans(text: str, spans: list[ResolvedSpan]) -> tuple[str, int]:
    return _apply_stub_spans(text, spans)


def extract_identity_evidence(
    record: RecordEnvelope,
    fallback_text: str | None = None,
) -> IdentityEvidence:
    """Return raw in-memory evidence for one envelope.

    The fallback exists only for the temporary stub, which consumes flattened text. The
    real implementation should classify `record.fields`, channels and `record.free_text`
    directly and ignore the fallback.
    """
    if fallback_text is None:
        fallback_text = record.free_text or " ".join(
            str(field.value) for field in record.fields if field.value is not None
        )
    return extract_identity_evidence_stub(record.record_id, fallback_text)
