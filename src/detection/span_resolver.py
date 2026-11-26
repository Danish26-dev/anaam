"""D3: resolve overlapping span candidates into non-overlapping edits.

Priority (lower tier wins):
  1 direct identifier  >  2 explicit identity  >  3 quasi-identifier (dates, ages)
  >  4 protected clinical value  >  5 weak name hypothesis

Rules:
  * Among edits, the higher-priority span is accepted first. A lower-priority edit that
    overlaps it is split around it; leftover pieces that are only punctuation or relation
    markers ("C/O", "S/o") are dropped.
  * A protected span blocks an overlapping edit of a weaker tier (a weak name inside
    "Dr. Ramesh Srivastava" or "Jeevan Jyoti Charitable Hospital" is dropped).
    Edits of tiers 1-3 always win: an Aadhaar or a date inside a clinical clause is still
    transformed.
  * Output is sorted and deterministic for the same input.
"""
from __future__ import annotations

import re

from .. import contracts as c

_DROP_REMAINDER = re.compile(
    r"^[\s\W_]*(?:[CSDWH][ ]?/[ ]?[Oo]|of|near|opp\.?|behind|Mr|Mrs|Ms|Smt|Shri|Sri|Dr|ji|the|and|&)?[\s\W_]*$",
    re.IGNORECASE,
)
_CATEGORY_RANK = {  # more specific categories win ties
    c.PATIENT_NAME: 0, c.RELATIVE_NAME: 1, c.AADHAAR: 0, c.ABHA_NUMBER: 0, c.PHONE: 1, c.EMAIL: 0,
    c.PAN: 0, c.INSURANCE_ID: 1, c.MRN: 2, c.DOB: 0, c.PERSON_NAME: 3, c.ADDRESS: 5,
}


def _priority(s: c.SpanCandidate):
    return (s.tier, -s.confidence, _CATEGORY_RANK.get(s.category, 4), -(s.end - s.start), s.start, s.category)


def _subtract(start: int, end: int, taken: list[tuple[int, int]]) -> list[tuple[int, int]]:
    pieces = [(start, end)]
    for ts, te in taken:
        nxt = []
        for ps, pe in pieces:
            if te <= ps or ts >= pe:
                nxt.append((ps, pe))
                continue
            if ps < ts:
                nxt.append((ps, ts))
            if te < pe:
                nxt.append((te, pe))
        pieces = nxt
    return pieces


def _trim_ws(text: str, s: int, e: int) -> tuple[int, int]:
    while s < e and text[s] in " \t\n,;:-":
        s += 1
    while e > s and text[e - 1] in " \t\n,;:-":
        e -= 1
    return s, e


def resolve(text: str, candidates: list[c.SpanCandidate]) -> list[c.SpanCandidate]:
    """Return the accepted edit spans (tiers 1, 2, 3, 5), non-overlapping, sorted by start."""
    edits = [s for s in candidates if s.proposed_action != c.KEEP and s.end > s.start]
    protected = [s for s in candidates if s.proposed_action == c.KEEP and s.end > s.start]
    accepted: list[c.SpanCandidate] = []
    taken: list[tuple[int, int]] = []
    for cand in sorted(edits, key=_priority):
        if cand.tier > c.TIER_PROTECTED and any(p.start < cand.end and cand.start < p.end for p in protected
                                                if p.tier < cand.tier):
            continue
        for ps, pe in _subtract(cand.start, cand.end, taken):
            ps, pe = _trim_ws(text, ps, pe)
            if pe <= ps:
                continue
            if (ps, pe) != (cand.start, cand.end) and _DROP_REMAINDER.match(text[ps:pe]):
                continue
            piece = c.SpanCandidate(ps, pe, cand.category, cand.role, cand.confidence, cand.tier,
                                    cand.source, cand.proposed_action)
            accepted.append(piece)
            taken.append((ps, pe))
    accepted.sort(key=lambda s: (s.start, s.end))
    return accepted


def protected_spans(candidates: list[c.SpanCandidate], edits: list[c.SpanCandidate]) -> list[c.SpanCandidate]:
    """Protected spans that survive the edits untouched (used by the clinical verifier)."""
    out = []
    for p in candidates:
        if p.proposed_action != c.KEEP:
            continue
        if not any(e.start < p.end and p.start < e.end for e in edits):
            out.append(p)
    return out


def to_resolved(spans: list[c.SpanCandidate], view, field_path: str = "",
                attrs_for=None) -> list[c.ResolvedSpan]:
    """Map accepted spans from view offsets to original offsets."""
    out = []
    for s in spans:
        a, b = view.span_to_original(s.start, s.end)
        attrs = attrs_for(s) if attrs_for else {}
        out.append(c.ResolvedSpan(a, b, s.category, s.proposed_action, s.source, field_path, None, attrs))
    return out
