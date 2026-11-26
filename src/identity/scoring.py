"""O7: conservative pair scoring with hard and soft conflict handling."""
from __future__ import annotations

from dataclasses import dataclass

from core.interfaces import IdentityEvidence
from .blocking import CandidatePair
from .canonicalize import canonical_dob, canonical_name_tokens, canonical_phone

STRONG_ID_TYPES = ("AADHAAR", "ABHA_NUMBER", "PAN")


@dataclass
class PairVerdict:
    record_a: str
    record_b: str
    link: bool
    reason_codes: list[str]
    hard_conflict: bool
    strength: str = "NONE"  # MUST | PROBABLE | NONE


def _national_id_conflict(a: IdentityEvidence, b: IdentityEvidence) -> bool:
    return any(
        a.national_ids[identifier_type] != b.national_ids[identifier_type]
        for identifier_type in set(a.national_ids) & set(b.national_ids)
    )


def _scoped_values(evidence: IdentityEvidence) -> dict[str, set[str]]:
    values: dict[str, set[str]] = {}
    for identifier in evidence.scoped_ids:
        values.setdefault(identifier.system, set()).add(identifier.value)
    return values


def _scoped_id_conflict(a: IdentityEvidence, b: IdentityEvidence) -> bool:
    a_values, b_values = _scoped_values(a), _scoped_values(b)
    return any(a_values[system].isdisjoint(b_values[system]) for system in set(a_values) & set(b_values))


def has_hard_conflict(a: IdentityEvidence, b: IdentityEvidence) -> bool:
    """Compare evidence directly; callers need not have generated a candidate pair."""
    return _national_id_conflict(a, b) or _scoped_id_conflict(a, b)


def _has_shared_strong_id(a: IdentityEvidence, b: IdentityEvidence) -> bool:
    for identifier_type in STRONG_ID_TYPES:
        value_a, value_b = a.national_ids.get(identifier_type), b.national_ids.get(identifier_type)
        if value_a and value_b and value_a == value_b:
            return True
    a_scoped = {(identifier.system, identifier.value) for identifier in a.scoped_ids}
    b_scoped = {(identifier.system, identifier.value) for identifier in b.scoped_ids}
    return bool(a_scoped & b_scoped)


def _canonical_names(values: list[str]) -> set[tuple[str, ...]]:
    return {tokens for value in values if (tokens := canonical_name_tokens(value))}


def _shared_name(a: IdentityEvidence, b: IdentityEvidence) -> bool:
    return bool(_canonical_names(a.patient_names) & _canonical_names(b.patient_names))


def _dob_match(a: IdentityEvidence, b: IdentityEvidence) -> bool:
    date_a, date_b = canonical_dob(a.date_of_birth or ""), canonical_dob(b.date_of_birth or "")
    return bool(date_a and date_b and date_a == date_b)


def _relative_match(a: IdentityEvidence, b: IdentityEvidence) -> bool:
    return bool(_canonical_names(a.relative_names) & _canonical_names(b.relative_names))


def _village_age_compatible(a: IdentityEvidence, b: IdentityEvidence) -> bool:
    if not a.village or not b.village or a.village.casefold() != b.village.casefold():
        return False
    return a.age is not None and b.age is not None and abs(a.age - b.age) <= 1


def _phone_match(a: IdentityEvidence, b: IdentityEvidence) -> bool:
    phones_a = {canonical_phone(phone) for phone in a.phones}
    phones_b = {canonical_phone(phone) for phone in b.phones}
    return any(len(phone) == 10 for phone in phones_a & phones_b)


def soft_conflict_codes(a: IdentityEvidence, b: IdentityEvidence) -> list[str]:
    codes: list[str] = []
    if a.gender and b.gender and a.gender.strip().casefold() != b.gender.strip().casefold():
        codes.append("soft_gender_mismatch")
    if a.age is not None and b.age is not None and abs(a.age - b.age) > 2:
        codes.append("soft_age_mismatch")

    if a.district and b.district:
        if a.district.strip().casefold() != b.district.strip().casefold():
            codes.append("soft_district_mismatch")
    elif a.village and b.village and a.village.strip().casefold() != b.village.strip().casefold():
        codes.append("soft_village_mismatch")

    if a.relative_names and b.relative_names and not _relative_match(a, b):
        codes.append("soft_relative_mismatch")
    return codes


def score_pair(pair: CandidatePair, a: IdentityEvidence, b: IdentityEvidence) -> PairVerdict:
    if has_hard_conflict(a, b):
        return PairVerdict(
            pair.record_a, pair.record_b, False,
            ["hard_conflict_id_mismatch"], True, "NONE",
        )

    soft_conflicts = soft_conflict_codes(a, b)
    if _has_shared_strong_id(a, b):
        # A shared unique identifier outranks demographic data-entry errors, but soft
        # conflicts remain in the ledger for review.
        return PairVerdict(
            pair.record_a, pair.record_b, True,
            ["shared_strong_identifier", *soft_conflicts], False, "MUST",
        )

    if _shared_name(a, b):
        supporting_clues: list[str] = []
        if _dob_match(a, b):
            supporting_clues.append("dob_match")
        if _relative_match(a, b):
            supporting_clues.append("relative_match")
        if _village_age_compatible(a, b):
            supporting_clues.append("village_age_match")

        if supporting_clues:
            strength = "PROBABLE" if soft_conflicts else "MUST"
            return PairVerdict(
                pair.record_a, pair.record_b, True,
                ["shared_name", *supporting_clues, *soft_conflicts], False, strength,
            )
        if _phone_match(a, b):
            return PairVerdict(
                pair.record_a, pair.record_b, True,
                ["shared_name", "shared_phone", *soft_conflicts], False, "PROBABLE",
            )
        return PairVerdict(
            pair.record_a, pair.record_b, False,
            ["shared_name_no_supporting_clue", *soft_conflicts], False, "NONE",
        )

    if _phone_match(a, b):
        return PairVerdict(
            pair.record_a, pair.record_b, False,
            ["phone_only_insufficient", *soft_conflicts], False, "NONE",
        )

    return PairVerdict(
        pair.record_a, pair.record_b, False,
        ["no_supporting_evidence", *soft_conflicts], False, "NONE",
    )
