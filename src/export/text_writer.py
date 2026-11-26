"""O5: text/free-text candidate writer."""
from __future__ import annotations

import dataclasses
import datetime as dt
import re

from core.interfaces import REENCODE, SHIFT_DATE, ResolvedSpan
from detection.api import apply_spans, field_spans, resolve_spans
from privacy.date_shift import shift_date, shift_date_string

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


_NUMERIC_DATE_RE = re.compile(r"^(\d{1,4})([-/. ])(\d{1,2})\2(\d{2,4})$")


def _pad(value: int, original: str) -> str:
    return str(value).zfill(len(original)) if len(original) > 1 else str(value)


def _shift_like(surface: str, iso: str, offset_days: int) -> str | None:
    """Shift a numeric date by offset_days, keeping its separator, field order and widths."""
    m = _NUMERIC_DATE_RE.match(surface)
    if not m:
        return None
    try:
        year, month, day = (int(x) for x in iso.split("-"))
        new = shift_date(dt.date(year, month, day), offset_days)
    except ValueError:
        return None
    if new is None:
        return None
    a, sep, b, last = m.groups()
    yy = f"{new.year:04d}" if len(last) == 4 else f"{new.year % 100:02d}"  # year is last unless ymd
    if len(a) == 4:
        return f"{new.year:04d}{sep}{_pad(new.month, b)}{sep}{_pad(new.day, last)}"
    if int(a) == day and int(b) == month:
        return f"{_pad(new.day, a)}{sep}{_pad(new.month, b)}{sep}{yy}"
    if int(a) == month and int(b) == day:
        return f"{_pad(new.month, a)}{sep}{_pad(new.day, b)}{sep}{yy}"
    return None


def _shifted_date_span(text: str, span: ResolvedSpan, offset_days: int) -> ResolvedSpan:
    """SHIFT_DATE span -> a replacement span holding the shifted date. A DOB that cannot be
    shifted is redacted; any other date is kept."""
    if span.action != SHIFT_DATE:
        return span
    iso = span.attrs.get("date") if span.attrs else None
    if offset_days and iso:
        shifted = _shift_like(text[span.start:span.end], iso, offset_days)
        if shifted is not None:
            return dataclasses.replace(span, action=REENCODE, replacement=shifted)
    return span


def render_text(
    text: str,
    date_offset_days: int = 0,
    record_id: str | None = None,
    field_path: str | None = None,
) -> tuple[str, int]:
    """Sanitize one value. With `record_id` and `field_path`, the engine's per-field spans
    (computed on the original value, with field classification) are applied first and dates
    are shifted afterwards; without context the value is scanned on its own."""
    spans = field_spans(record_id, field_path, text)
    if spans is not None:
        # The engine found the dates, so they are shifted through its spans; running the
        # regex pass afterwards would shift a slash date twice.
        spans = [_shifted_date_span(text, s, date_offset_days) for s in spans]
        return apply_spans(text, spans)
    shifted_text, _ = _shift_free_text_dates(text, date_offset_days)
    spans = resolve_spans(shifted_text)
    return apply_spans(shifted_text, spans)


_PATIENT_LABEL_RE = re.compile(
    r"(?im)^(\s*(?:patient(?:\s+name)?|name|नाम)\s*[:=\-]\s*)[^\r\n]+"
)


def render_text_document(
    text: str, pseudonym: str | None, date_offset_days: int = 0,
    record_id: str | None = None,
) -> tuple[str, int]:
    """Render a document and embed any claimed pseudonym in an identity location.

    Explicit patient/name labels are replaced in place. If a linked document has no such
    label, a safe `Patient:` header is prepended so records.jsonl never claims a pseudonym
    that is absent from the released record.
    """
    rendered, count = render_text(text, date_offset_days, record_id, "" if record_id else None)
    if pseudonym is None:
        return rendered, count
    rendered, replacements = _PATIENT_LABEL_RE.subn(
        lambda match: f"{match.group(1)}{pseudonym}", rendered, count=1
    )
    if replacements:
        return rendered, count + 1
    return f"Patient: {pseudonym}\n{rendered}", count + 1
