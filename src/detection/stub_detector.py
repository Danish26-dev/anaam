"""Temporary stand-in for Danish's detection stack.

This is NOT part of Omkar's owned scope -- it exists only so the pipeline is runnable and
testable end-to-end before src/detection/{clinical,identifiers,names,...}.py exist. It
implements the same call shape Danish's real span resolver and identity extractor will
have, so main.py never needs to change when the real modules land: only this module gets
swapped out (or deleted once Danish's own modules satisfy the same functions).

Behaviour: regex-only, same rough level as the official starter. It intentionally does
NOT try to be clever about clinical spans, multilingual names, or hidden channels --
that is explicitly Danish's job, not something Omkar's pipeline should pre-empt.
"""
from __future__ import annotations

import re

from core.interfaces import IdentityEvidence, REDACT, REENCODE, ResolvedSpan

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("PHONE", re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")),
    ("AADHAAR", re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")),
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
]


def resolve_spans_in_text(text: str) -> list[ResolvedSpan]:
    """Minimal regex-only span resolution. Real resolution (clinical protection, context
    rules, overlap handling) is Danish's D3 span_resolver.py.
    """
    spans: list[ResolvedSpan] = []
    for category, rx in _PATTERNS:
        for m in rx.finditer(text):
            spans.append(
                ResolvedSpan(start=m.start(), end=m.end(), category=category, action=REDACT, reason_code="stub_regex")
            )
    spans.sort(key=lambda s: s.start)
    return spans


def apply_resolved_spans(text: str, spans: list[ResolvedSpan]) -> tuple[str, int]:
    """Replace each resolved span with a typed placeholder, right-to-left so earlier
    offsets stay valid. Returns (new_text, count_redacted).

    Only understands REDACT (the stub never emits anything else). REENCODE spans with a
    precomputed `replacement` are honoured too, since any upstream caller -- including
    Danish's real engine once api.py is wired to it -- may already produce those; every
    other action is intentionally left untouched here rather than silently treated as
    safe-to-skip. That keeps this function honest about what it does and does not redact
    once real spans start flowing through the same call site.
    """
    out = text
    count = 0
    for span in sorted(spans, key=lambda s: s.start, reverse=True):
        if span.action == REDACT:
            out = out[: span.start] + f"[{span.category}]" + out[span.end :]
            count += 1
        elif span.action == REENCODE and span.replacement is not None:
            out = out[: span.start] + span.replacement + out[span.end :]
            count += 1
    return out, count


def extract_identity_evidence_stub(record_id: str, text: str) -> IdentityEvidence:
    """Placeholder identity extraction: finds nothing. Real extraction is Danish's job
    (D6 names.py + O6 consuming IdentityEvidence). Returning an empty-but-valid
    IdentityEvidence keeps O6/O7 runnable without special-casing "no detector yet".
    """
    return IdentityEvidence(record_id=record_id)
