"""D4: address components.

Two entry points:
  * `detect_address_components(text)` finds labelled parts anywhere in free text
    (house numbers, mohallas, landmarks, villages after "Gram", tehsils, districts, PINs).
  * `address_segments(text, start, end)` classifies a known address span (an "Address:"
    line or a structured address field) segment by segment. It is a whitelist: tehsil,
    district, state and PIN segments are kept or generalized, and every other segment is
    redacted, so an unseen locality format cannot leak through.
"""
from __future__ import annotations

import re

from core import interfaces as c
from .gazetteer_data import STATES, UP_DISTRICTS
from .normalization import DEVANAGARI_LETTERS as DL

_LAT_WORD = r"[A-Z][A-Za-z'\.]*"
_LAT_NAME = rf"{_LAT_WORD}(?:[ ]+{_LAT_WORD}){{0,3}}"
_DEV_NAME = rf"[{DL}]+(?:[ ]+[{DL}]+){{0,3}}"

HOUSE = re.compile(
    r"\b(?:H\.?[ \t]?No\.?|House(?:[ \t]?No\.?)?|Makan(?:[ \t]?(?:No\.?|Number))?|Plot(?:[ \t]?No\.?)?|"
    r"Flat(?:[ \t]?No\.?)?|Door[ \t]?No\.?|Qr\.?[ \t]?No\.?|Quarter(?:[ \t]?No\.?)?|Ghar[ \t]?(?:No\.?)?|"
    r"Bungalow(?:[ \t]?No\.?)?|Room[ \t]?No\.?|Apt\.?|Apartment|Tower|Sector)"
    r"[ \t]*[:\-#]?[ \t]*\d+[A-Za-z]?(?:[ \t]?[/\-][ \t]?\d+[A-Za-z]?)?(?![\d])",
    re.IGNORECASE,
)
HOUSE_DEVA = re.compile(rf"(?:मकान|घर|प्लॉट)[ \t]*(?:नं|नंबर|संख्या|न|सं)\.?[ \t]*\d+(?:[ \t]?[/\-][ \t]?\d+)?")
LOCALITY = re.compile(rf"\b(?:Mohalla|Mohallah|Muhalla|Mohala|Mohulla|Mohl\.)[ ]*[:\-]?[ ]*{_LAT_NAME}")
LOCALITY_DEVA = re.compile(rf"मोहल्ला[ ]*[:\-]?[ ]*{_DEV_NAME}")
LANDMARK = re.compile(
    rf"\b(?:near|Near|NEAR|nr\.|Nr\.|opp\.|Opp\.|opposite|Opposite|behind|Behind|beside|Beside|"
    rf"in front of|In front of|next to|Next to|close to|Close to)[ \t]+{_LAT_NAME}"
)
LANDMARK_DEVA = re.compile(
    rf"(?:[{DL}]+[ \t]+){{1,3}}के[ \t]+(?:पीछे|पास|सामने|बगल|नज़दीक|नजदीक|निकट)")
VILLAGE = re.compile(
    rf"\b(?:Gram|Graam|Gaon|Village|Vill\.|Vill|Mauza|Mouza|Grm\.)[ ]*[:\-]?[ ]*({_LAT_NAME})"
)
VILLAGE_DEVA = re.compile(rf"(?:ग्राम|गाँव|गांव|मौजा)[ ]*[:\-]?[ ]*({_DEV_NAME})")
TEHSIL = re.compile(
    rf"\b(?:Tehsil|Tahsil|Teh\.|Tah\.|Block)[ ]*[:\-]?[ ]*({_LAT_NAME})"
    rf"|(?:तहसील|ब्लॉक)[ ]*[:\-]?[ ]*({_DEV_NAME})"
)
DISTRICT = re.compile(
    rf"\b(?:Distt\.|Distt|Dist\.|District|Zila|Jila|Janpad)[ ]*[:\-]?[ ]*({_LAT_NAME})"
    rf"|(?:जिला|ज़िला|जनपद)[ ]*[:\-]?[ ]*({_DEV_NAME})"
)
PIN_LABELLED = re.compile(
    r"(?:\bPIN|\bPin|\bpin|\bPincode|\bPIN[ \t]?Code|\bPin[ \t]?Code|\bZip|\bZIP|\bzip|\bPostal[ \t]?Code|पिन(?:[ \t]?कोड)?)"
    r"[ \t]*(?:code|Code|No\.?)?[ ]*[:\-]?[ ]*(\d{6})(?!\d)"
)
PIN_AFTER_DISTRICT = re.compile(
    rf"(?:\bDistt?\.?|\bDistrict|जिला|ज़िला)[ \t]*[^\n,\d]{{2,30}}?[ \t]*[\-–,][ \t]*(\d{{6}})(?!\d)")
ADDRESS_LINE = re.compile(
    r"(?:^|(?<=\n)|(?<=[ \t]{2}))"
    r"(?:Address|ADDRESS|Addr\.|Residential Address|Permanent Address|Present Address|Home Address|"
    r"Residence|RESIDENCE|Resides at|Domicile|Home|Res\.|Pata|पता|निवास|निवासी|R/o|r/o|R/O|Resident of)"
    r"(?:[ \t]*\([^)\n]{0,30}\))?[ \t]*[:\-][ \t]*([^\n]+)"
)
_RELATION_HEAD = re.compile(r"^(?:C|S|W|D|H)[ \t]?/[ \t]?O\b|^(?:Care of)\b", re.IGNORECASE)
_WARD = re.compile(r"^Ward[ \t]*(?:No\.?[ \t]*)?\d+[A-Z]?$", re.IGNORECASE)
_PIN_ONLY = re.compile(r"^(?:PIN[ \t:\-]*)?\d{6}$", re.IGNORECASE)
_PLACE_KEYS = {k.casefold() for k in UP_DISTRICTS + STATES}
# segment that is only placeholders, optionally behind a label word: "[LOCALITY]", "ग्राम [VILLAGE]"
_SANITIZED = re.compile(r"(?:[A-Za-z./\u0900-\u097F]+[ \t]+)?(?:\[[A-Z\-]+\][ \t]*)+")


def _cand(s, e, cat, source, action=c.REDACT, conf=0.9):
    return c.SpanCandidate(s, e, cat, "patient", conf, c.TIER_EXPLICIT_IDENTITY, source, action)


def _keep(s, e, cat, source):
    return c.SpanCandidate(s, e, cat, None, 0.8, c.TIER_PROTECTED, source, c.KEEP)


def _group_span(m):
    for g in range(1, (m.re.groups or 0) + 1):
        if m.group(g):
            return m.start(g), m.end(g)
    return m.start(), m.end()


def detect_address_components(text: str) -> list[c.SpanCandidate]:
    out: list[c.SpanCandidate] = []
    for rx in (HOUSE, HOUSE_DEVA):
        for m in rx.finditer(text):
            out.append(_cand(m.start(), m.end(), c.HOUSE, "house"))
    for rx in (LOCALITY, LOCALITY_DEVA):
        for m in rx.finditer(text):
            out.append(_cand(m.start(), m.end(), c.LOCALITY, "locality"))
    for rx in (LANDMARK, LANDMARK_DEVA):
        for m in rx.finditer(text):
            out.append(_cand(m.start(), m.end(), c.LANDMARK, "landmark", conf=0.8))
    for rx in (VILLAGE, VILLAGE_DEVA):
        for m in rx.finditer(text):
            s, e = _group_span(m)
            out.append(_cand(s, e, c.VILLAGE, "village", c.GENERALIZE_LOCATION))
    for m in TEHSIL.finditer(text):
        s, e = _group_span(m)
        out.append(_keep(s, e, c.TEHSIL, "tehsil"))
    for m in DISTRICT.finditer(text):
        s, e = _group_span(m)
        out.append(_keep(s, e, c.DISTRICT, "district"))
    for rx in (PIN_LABELLED, PIN_AFTER_DISTRICT):
        for m in rx.finditer(text):
            out.append(_cand(m.start(1), m.end(1), c.PIN, "pin", c.GENERALIZE_PIN))
    for m in ADDRESS_LINE.finditer(text):
        out.extend(address_segments(text, m.start(1), m.end(1), source="address_line"))
    return out


def address_segments(text: str, start: int, end: int, source: str = "address_field") -> list[c.SpanCandidate]:
    """Classify every comma-separated segment of text[start:end]."""
    out: list[c.SpanCandidate] = []
    pos = start
    for raw in re.split(r"(,|;|\|)", text[start:end]):
        seg_start, seg_end = pos, pos + len(raw)
        pos = seg_end
        if raw in (",", ";", "|"):
            continue
        lead = len(raw) - len(raw.lstrip())
        trail = len(raw) - len(raw.rstrip())
        s, e = seg_start + lead, seg_end - trail
        if s >= e:
            continue
        seg = text[s:e]
        out.extend(_classify_segment(text, s, e, seg, source))
    return out


def _classify_segment(text, s, e, seg, source) -> list[c.SpanCandidate]:
    # "Distt. Barabanki - 233433": district plus PIN
    pin_tail = re.search(r"[ \t]*[\-–][ \t]*(\d{6}|\d{3}\*{3})$", seg)
    out = []
    if pin_tail:
        if pin_tail.group(1).isdigit():       # an already generalized "226***" needs no edit
            out.append(_cand(s + pin_tail.start(1), s + pin_tail.end(1), c.PIN, source, c.GENERALIZE_PIN))
        e = s + pin_tail.start()
        seg = text[s:e]
    if not seg.strip():
        return out
    if _SANITIZED.fullmatch(seg.strip()):     # "[HOUSE]", "Gram [VILLAGE]": already handled
        return out
    dm = DISTRICT.match(seg) or TEHSIL.match(seg)
    if dm:
        g0, g1 = _group_span(dm)
        if dm.re is DISTRICT:
            out.append(_keep(s + g0, s + g1, c.DISTRICT, source))
        else:
            out.append(_keep(s + g0, s + g1, c.TEHSIL, source))
        rest = seg[dm.end():].strip()
        if rest:  # trailing words that are not part of the name: redact to be safe
            r0 = s + seg.index(rest, dm.end())
            out.append(_cand(r0, r0 + len(rest), c.ADDRESS, source))
        return out
    if seg.strip().casefold() in _PLACE_KEYS:
        out.append(_keep(s, e, c.DISTRICT, source))
        return out
    if _PIN_ONLY.match(seg.strip()):
        digits = re.search(r"\d{6}", seg)
        out.append(_cand(s + digits.start(), s + digits.end(), c.PIN, source, c.GENERALIZE_PIN))
        return out
    vm = VILLAGE.match(seg) or VILLAGE_DEVA.match(seg)
    if vm:
        g0, g1 = _group_span(vm)
        out.append(_cand(s + g0, s + g1, c.VILLAGE, source, c.GENERALIZE_LOCATION))
        return out
    if HOUSE.match(seg) or HOUSE_DEVA.match(seg):
        out.append(_cand(s, e, c.HOUSE, source))
        return out
    if LOCALITY.match(seg) or LOCALITY_DEVA.match(seg) or _WARD.match(seg.strip()):
        out.append(_cand(s, e, c.LOCALITY, source))
        return out
    if LANDMARK.match(seg) or LANDMARK_DEVA.search(seg):
        out.append(_cand(s, e, c.LANDMARK, source))
        return out
    if _RELATION_HEAD.match(seg.strip()):
        out.append(_cand(s, e, c.ADDRESS, source))   # names module types the relative
        return out
    out.append(_cand(s, e, c.ADDRESS, source, conf=0.75))
    return out
