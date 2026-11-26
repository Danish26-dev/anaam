"""O6: deterministic, bounded identity candidate generation."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from core.interfaces import IdentityEvidence
from .canonicalize import (
    canonical_dob,
    canonical_name_tokens,
    canonical_phone,
    phonetic_name_key,
)

# Hidden datasets are small, but malformed/high-frequency fields must not cause O(n²)
# work. Large strong-ID blocks use a deterministic star (enough to connect one identity);
# large weak blocks are skipped so the system abstains instead of over-linking.
MAX_BLOCK_MEMBERS = 100
MAX_CANDIDATE_PAIRS = 100_000


@dataclass(frozen=True)
class CandidatePair:
    record_a: str
    record_b: str
    blocking_key: str


def _add_block(index: dict[str, list[str]], key: str | None, record_id: str) -> None:
    if key:
        index[key].append(record_id)


def generate_candidates(evidence_by_record: dict[str, IdentityEvidence]) -> list[CandidatePair]:
    national_id_index: dict[str, list[str]] = defaultdict(list)
    scoped_id_index: dict[str, list[str]] = defaultdict(list)
    phone_index: dict[str, list[str]] = defaultdict(list)
    name_dob_index: dict[str, list[str]] = defaultdict(list)
    name_relative_index: dict[str, list[str]] = defaultdict(list)
    name_location_index: dict[str, list[str]] = defaultdict(list)
    name_only_index: dict[str, list[str]] = defaultdict(list)
    phonetic_index: dict[str, list[str]] = defaultdict(list)

    for record_id in sorted(evidence_by_record):
        evidence = evidence_by_record[record_id]

        for identifier_type, value in sorted(evidence.national_ids.items()):
            _add_block(national_id_index, f"{identifier_type}:{value}", record_id)
        for scoped in sorted(evidence.scoped_ids, key=lambda item: (item.system, item.value)):
            _add_block(scoped_id_index, f"{scoped.system}:{scoped.value}", record_id)
        for phone in sorted(evidence.phones):
            canonical = canonical_phone(phone)
            if len(canonical) == 10:
                _add_block(phone_index, canonical, record_id)

        for name in evidence.patient_names:
            _add_block(phonetic_index, phonetic_name_key(name), record_id)
        name_keys = sorted({canonical_name_tokens(name) for name in evidence.patient_names if name})
        dob_key = canonical_dob(evidence.date_of_birth or "")
        location_key = (evidence.village or evidence.tehsil or evidence.district or "").strip().casefold()
        for name_tokens in name_keys:
            if not name_tokens:
                continue
            name_key = " ".join(name_tokens)
            _add_block(name_only_index, name_key, record_id)
            if dob_key:
                _add_block(name_dob_index, f"{name_key}|{dob_key}", record_id)
            if location_key:
                _add_block(name_location_index, f"{name_key}|{location_key}", record_id)
            for relative in evidence.relative_names:
                relative_tokens = canonical_name_tokens(relative)
                if relative_tokens:
                    _add_block(
                        name_relative_index,
                        f"{name_key}|{' '.join(relative_tokens)}",
                        record_id,
                    )

    pair_tags: dict[tuple[str, str], set[str]] = {}

    def add_pair(a: str, b: str, tag: str, key: str) -> bool:
        pair = (a, b) if a < b else (b, a)
        if pair not in pair_tags and len(pair_tags) >= MAX_CANDIDATE_PAIRS:
            return False
        pair_tags.setdefault(pair, set()).add(f"{tag}:{key}")
        return True

    def emit(index: dict[str, list[str]], tag: str, allow_large_star: bool = False) -> None:
        for key in sorted(index):
            members = sorted(set(index[key]))
            if len(members) < 2:
                continue
            if len(members) > MAX_BLOCK_MEMBERS:
                if not allow_large_star:
                    continue
                candidate_pairs = ((members[0], member) for member in members[1:])
            else:
                candidate_pairs = combinations(members, 2)
            for record_a, record_b in candidate_pairs:
                if not add_pair(record_a, record_b, tag, key):
                    return

    emit(national_id_index, "national_id", allow_large_star=True)
    emit(scoped_id_index, "scoped_id", allow_large_star=True)
    emit(phone_index, "phone")
    emit(name_dob_index, "name_dob")
    emit(name_relative_index, "name_relative")
    emit(name_location_index, "name_location")
    emit(name_only_index, "name_only")
    emit(phonetic_index, "phonetic")

    return [
        CandidatePair(record_a, record_b, "|".join(sorted(tags)))
        for (record_a, record_b), tags in sorted(pair_tags.items())
    ]
