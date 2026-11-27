"""A3: local Sweeney-style record linkage approximation.

Filters registry candidates in the documented evidence order. A contradictory filter is
skipped instead of emptying the candidate set, matching the published attacker behavior.
The tool remains a local directional measurement, not the official score.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

from .common import ReleaseRecord, RegistryPerson, extract_age_candidates, extract_pins

_NAME_FULL_WEIGHT = 60
_NAME_GIVEN_WEIGHT = 8
_NAME_SURNAME_WEIGHT = 3
_RELATIVE_WEIGHT = 8
_HOUSE_WEIGHT = 2

_PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?([6-9]\d{4}[\s-]?\d{5})(?!\d)")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.IGNORECASE)
_MASKED_AADHAAR_RE = re.compile(r"(?:X[\s-]*){8}(\d{4})", re.IGNORECASE)
_GENDER_RE = re.compile(r"(?:\b(?:gender|sex)\s*[:=]\s*|\d{1,3}\s*[/|]\s*)([MF])\b", re.IGNORECASE)

# docs/ATTACKS.md: "names via transliteration-aware token lookup (doctors after `Dr.`
# are skipped)". A doctor line keeps "Dr. Ramesh Srivastava" by design (the clinical
# shield protects doctor names), and a token match against that name is not a patient
# identifier leak. Mask out the word(s) immediately after a doctor honorific so a
# registry name collision there cannot contribute to a candidate's score, mirroring the
# documented attacker rather than the weaker approximation this file shipped with.
_DOCTOR_LINE_RE = re.compile(
    r"\b(?:dr\.?|doctor|seen\s+by|referred\s+by|consultant)\s*[:\-]?\s*"
    r"([a-z][a-z.']*(?:\s+[a-z][a-z.']*){0,3})",
    re.IGNORECASE,
)


def _mask_doctor_names(text_lower: str) -> str:
    return _DOCTOR_LINE_RE.sub(lambda m: m.group(0)[: m.start(1) - m.start(0)] + "\u2022" * len(m.group(1)), text_lower)


# One record's text is scored against every registry candidate in a tight loop (A3 and
# A4 both do this); re-running the doctor-masking regex per candidate would be wasted
# work on the same string, so cache it by identity of the input text for this process.
_mask_doctor_names_cached = lru_cache(maxsize=512)(_mask_doctor_names)

# docs/ATTACKS.md: the attacker reads "(field, value) pairs (CSV header -> cell, JSON key
# -> leaf, free text)" and extracts evidence FROM THOSE FIELDS, not by scanning raw
# digits anywhere in the pooled text. A bare house number (e.g. "167") coincidentally
# equal to a lab value, a dose, an HbA1c result or a day count is not address evidence,
# and crediting it as one let a single clinical-number coincidence alone cross the
# re-identification confidence threshold on records with no real address present at all
# (see docs/PROGRESS.md "house-number signal" finding). Require the match to sit near an
# address-shaped label, same restriction the field-aware attacker would have for a
# free-text line and the only place CSV/JSON house-like fields appear in the flattened
# "key: value" text this tool's records are built from (see load_release.py).
_ADDRESS_CONTEXT_RE = re.compile(
    r"(?:h\.?\s*no\.?|house(?:\s*no\.?)?|makan|plot(?:\s*no\.?)?|flat(?:\s*no\.?)?|"
    r"door\s*no\.?|qr\.?\s*no\.?|quarter(?:\s*no\.?)?|ghar(?:\s*no\.?)?|address|"
    r"pata|house_no|house_number|plot_no)\s*[:\-.]?\s*$",
    re.IGNORECASE,
)
_HOUSE_CONTEXT_WINDOW = 24  # chars of context immediately before the matched number


def _house_number_in_address_context(text_lower: str, house: str) -> bool:
    for match in re.finditer(rf"\b{re.escape(house)}\b", text_lower):
        window_start = max(0, match.start() - _HOUSE_CONTEXT_WINDOW)
        if _ADDRESS_CONTEXT_RE.search(text_lower[window_start:match.start()]):
            return True
    return False


def _candidate_score(text_lower: str, person: RegistryPerson) -> float:
    text_lower = _mask_doctor_names_cached(text_lower)
    score = 0.0
    full_name = person.name.strip().casefold()
    name_tokens = full_name.split()
    if full_name and full_name in text_lower:
        score += _NAME_FULL_WEIGHT
    else:
        if name_tokens and len(name_tokens[0]) > 2 and name_tokens[0] in text_lower:
            score += _NAME_GIVEN_WEIGHT
        if len(name_tokens) > 1 and len(name_tokens[-1]) > 2 and name_tokens[-1] in text_lower:
            score += _NAME_SURNAME_WEIGHT
    relative = person.relative_name.strip().casefold()
    if relative and len(relative) > 2 and relative in text_lower:
        score += _RELATIVE_WEIGHT
    house = person.house_no.strip().casefold()
    if house and _house_number_in_address_context(text_lower, house):
        score += _HOUSE_WEIGHT
    return score


def _extract_phones(text: str) -> set[str]:
    return {re.sub(r"\D", "", match)[-10:] for match in _PHONE_RE.findall(text)}


def _skip_empty_filter(
    candidates: list[RegistryPerson], predicate: Callable[[RegistryPerson], bool]
) -> list[RegistryPerson]:
    filtered = [person for person in candidates if predicate(person)]
    return filtered or candidates


def _registry_values_in_text(
    text_lower: str, registry: list[RegistryPerson], attribute: str
) -> set[str]:
    values = {
        str(getattr(person, attribute)).strip().casefold()
        for person in registry
        if str(getattr(person, attribute)).strip()
    }
    return {value for value in values if len(value) > 2 and value in text_lower}


@dataclass
class A3Result:
    mean_top_candidate_share: float
    records_with_any_candidate: int
    total_records: int


def record_linkage(
    record: ReleaseRecord, registry: list[RegistryPerson]
) -> tuple[str | None, float]:
    text_lower = record.text.casefold()
    candidates = list(registry)

    phones = _extract_phones(record.text)
    emails = {email.casefold() for email in _EMAIL_RE.findall(record.text)}
    last4 = set(_MASKED_AADHAAR_RE.findall(record.text))
    districts = _registry_values_in_text(text_lower, registry, "district")
    genders = {value.upper() for value in _GENDER_RE.findall(record.text)}
    ages = extract_age_candidates(record.text)
    tehsils = _registry_values_in_text(text_lower, registry, "tehsil")
    villages = _registry_values_in_text(text_lower, registry, "village")
    pins = extract_pins(record.text)

    if phones:
        candidates = _skip_empty_filter(candidates, lambda person: person.phone in phones)
    if emails:
        candidates = _skip_empty_filter(candidates, lambda person: person.email.casefold() in emails)
    if last4:
        candidates = _skip_empty_filter(candidates, lambda person: person.aadhaar_last4 in last4)
    if districts:
        candidates = _skip_empty_filter(candidates, lambda person: person.district.casefold() in districts)
    if genders:
        candidates = _skip_empty_filter(candidates, lambda person: person.gender.upper() in genders)
    if ages:
        candidates = _skip_empty_filter(
            candidates,
            lambda person: person.age is not None and any(abs(person.age - age) <= 2 for age in ages),
        )
    if tehsils:
        candidates = _skip_empty_filter(candidates, lambda person: person.tehsil.casefold() in tehsils)
    if villages:
        candidates = _skip_empty_filter(candidates, lambda person: person.village.casefold() in villages)
    if pins:
        candidates = _skip_empty_filter(candidates, lambda person: person.pin in pins)

    scored = [(_candidate_score(text_lower, person), person.rid) for person in candidates]
    if not scored or max(score for score, _ in scored) <= 0:
        return None, 0.0
    top_score = max(score for score, _ in scored)
    top_rid = min(rid for score, rid in scored if score == top_score)
    return top_rid, top_score / sum(score for score, _ in scored)


def run_a3(records: list[ReleaseRecord], registry: list[RegistryPerson]) -> A3Result:
    linkages = [record_linkage(record, registry) for record in records]
    nonzero = [share for _rid, share in linkages if share > 0]
    return A3Result(
        mean_top_candidate_share=sum(nonzero) / len(nonzero) if nonzero else 0.0,
        records_with_any_candidate=len(nonzero),
        total_records=len(records),
    )
