"""O9: per-patient date shifting.

Every date belonging to one linked patient moves by the SAME offset, so stay lengths and
cross-event intervals are preserved exactly. Unlinked records (patient=None) still need a
deterministic, non-zero, record-specific shift -- using the same global shift for every
unlinked record would let an attacker recover it trivially (a global-shift attack), so we
key by record_id instead of a shared constant.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import re

from core.record_ids import content_anchor, stable_content_fingerprint

_DATE_SHIFT_PREFIX = b"shift|"


def shift_days_for_key(date_shift_key: bytes, identity_key: str, max_days: int) -> int:
    """Deterministic non-zero offset in [-max_days, +max_days]."""
    if max_days < 1:
        raise ValueError("date_shift_max_days_must_be_positive")
    digest = hmac.new(date_shift_key, _DATE_SHIFT_PREFIX + identity_key.encode("utf-8"), hashlib.sha256).digest()
    span = 2 * max_days
    v = (int.from_bytes(digest[:4], "big") % span) - max_days
    return v if v != 0 else 1


def shift_date(value: dt.date, offset_days: int) -> dt.date | None:
    """Shift a date, returning ``None`` rather than leaking the original on overflow."""
    try:
        return value + dt.timedelta(days=offset_days)
    except OverflowError:
        return None


_SLASH_DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})$")
_ISO_DATETIME_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})([T ].*)?$")


def build_date_offset_map(
    date_shift_key: bytes,
    assignments,
    max_days: int = 180,
) -> dict[str, int]:
    """Return ``record_id -> offset_days`` with stable cluster-level derivation.

    Linked records derive one offset from the duplicate-insensitive cluster fingerprint,
    so record order and duplicate files cannot change the shift. Unlinked records derive
    their offset from their duplicate-insensitive content anchor; exact duplicate records
    therefore sanitize consistently even before identity linkage exists.
    """
    members_by_cluster: dict[str, list[str]] = {}
    for assignment in assignments:
        if assignment.cluster_key is not None:
            members_by_cluster.setdefault(assignment.cluster_key, []).append(assignment.record_id)

    cluster_identity = {
        cluster_key: "cluster-v1|" + stable_content_fingerprint(members).hex()
        for cluster_key, members in members_by_cluster.items()
    }

    offsets: dict[str, int] = {}
    for assignment in assignments:
        identity_key = (
            cluster_identity[assignment.cluster_key]
            if assignment.cluster_key is not None
            else content_anchor(assignment.record_id)
        )
        offsets[assignment.record_id] = shift_days_for_key(date_shift_key, identity_key, max_days)
    return offsets


def shift_date_string(value: str, offset_days: int, date_hint: str = "dmy") -> str | None:
    """Shift a numeric date while preserving its original syntax.

    Supported forms are ISO ``YYYY-MM-DD`` (with an optional time/timezone suffix),
    ``DD/MM/YYYY``, ``DD/MM/YY``, ``MM/DD/YYYY`` and ``MM/DD/YY``. Slash dates use the
    ``date_hint`` value ``"dmy"`` or ``"mdy"``. ``"auto"`` accepts only an
    unambiguous slash date (one component greater than 12); ambiguous values return
    ``None`` rather than being guessed.
    """
    value = value.strip()

    iso_match = _ISO_DATETIME_RE.match(value)
    if iso_match:
        year, month, day, rest = iso_match.groups()
        try:
            shifted = shift_date(dt.date(int(year), int(month), int(day)), offset_days)
        except ValueError:
            return None
        if shifted is None:
            return None
        return f"{shifted.year:04d}-{shifted.month:02d}-{shifted.day:02d}{rest or ''}"

    slash_match = _SLASH_DATE_RE.match(value)
    if not slash_match:
        return None

    first_text, second_text, year_text = slash_match.groups()
    first, second = int(first_text), int(second_text)
    year_width = len(year_text)
    year_value = int(year_text)
    year = (
        2000 + year_value if year_width == 2 and year_value < 70
        else 1900 + year_value if year_width == 2
        else year_value
    )
    hint = date_hint.strip().lower()
    if hint == "dmy":
        day, month = first, second
    elif hint == "mdy":
        month, day = first, second
    elif hint == "auto":
        if first > 12 and second <= 12:
            day, month = first, second
            hint = "dmy"
        elif second > 12 and first <= 12:
            month, day = first, second
            hint = "mdy"
        else:
            return None
    else:
        return None

    try:
        shifted = shift_date(dt.date(year, month, day), offset_days)
    except ValueError:
        return None
    if shifted is None:
        return None
    year_output = (
        f"{shifted.year % 100:02d}" if year_width == 2 else f"{shifted.year:04d}"
    )
    if hint == "mdy":
        return f"{shifted.month:02d}/{shifted.day:02d}/{year_output}"
    return f"{shifted.day:02d}/{shifted.month:02d}/{year_output}"
