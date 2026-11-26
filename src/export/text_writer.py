"""O5: text/free-text candidate writer."""
from __future__ import annotations

import re

from detection.api import apply_spans, resolve_spans
from privacy.date_shift import shift_date_string

# Conservative free-text date patterns (O9): strict DD/MM/YY or DD/MM/YYYY and ISO
# dates. Slash dates follow this dataset's documented DMY convention. Deliberately does NOT try to shift every digit
# sequence that looks date-shaped -- that is how a lab value or a dose gets corrupted.
# Finding date SPANS inside unstructured prose more precisely (e.g. "admitted on 4th
# Feb") is Danish's clinical/context detection scope; this regex only catches the
# strict, unambiguous numeric forms the practice dataset actually uses in free text
# (discharge notes, prescriptions, nursing notes).
_FREE_TEXT_DMY_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2}(?:\d{2})?\b")
_FREE_TEXT_DMY_HYPHEN_RE = re.compile(r"\b\d{1,2}-\d{1,2}-\d{2}(?:\d{2})?\b")
_FREE_TEXT_ISO_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def _shift_free_text_dates(text: str, offset_days: int) -> tuple[str, int]:
    if not offset_days:
        return text, 0
    shifted_count = 0

    def _replace(match: re.Match) -> str:
        nonlocal shifted_count
        new_value = shift_date_string(match.group(0), offset_days)
        if new_value is None:
            return match.group(0)
        shifted_count += 1
        return new_value

    # ISO (YYYY-MM-DD) runs before the hyphenated DMY pattern so a 4-digit leading
    # component is always treated as a year, never misread as a 2-digit day/month by
    # the DMY-hyphen pattern re-matching whatever the ISO substitution left behind.
    text = _FREE_TEXT_ISO_RE.sub(_replace, text)
    text = _FREE_TEXT_DMY_RE.sub(_replace, text)
    text = _FREE_TEXT_DMY_HYPHEN_RE.sub(_replace, text)
    return text, shifted_count


def render_text(text: str, date_offset_days: int = 0) -> tuple[str, int]:
    shifted_text, _ = _shift_free_text_dates(text, date_offset_days)
    spans = resolve_spans(shifted_text)
    return apply_spans(shifted_text, spans)


_PATIENT_LABEL_RE = re.compile(
    r"(?im)^(\s*(?:patient(?:\s+name)?|name|नाम)\s*[:=\-]\s*)[^\r\n]+"
)


def render_text_document(
    text: str, pseudonym: str | None, date_offset_days: int = 0
) -> tuple[str, int]:
    """Render a document and embed any claimed pseudonym in an identity location.

    Explicit patient/name labels are replaced in place. If a linked document has no such
    label, a safe `Patient:` header is prepended so records.jsonl never claims a pseudonym
    that is absent from the released record.
    """
    rendered, count = render_text(text, date_offset_days)
    if pseudonym is None:
        return rendered, count
    rendered, replacements = _PATIENT_LABEL_RE.subn(
        lambda match: f"{match.group(1)}{pseudonym}", rendered, count=1
    )
    if replacements:
        return rendered, count + 1
    return f"Patient: {pseudonym}\n{rendered}", count + 1
