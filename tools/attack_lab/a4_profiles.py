"""A4: local profile-aggregation attack using maximal connected components."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .a3_linkage import _candidate_score
from .common import ReleaseRecord, RegistryPerson, extract_age_candidates, extract_pins

_REF_TOKEN_RE = re.compile(
    r"\b(?:UHID|MRN|IPD|IP|ADM|SNJ|JJH|DHH)[A-Z0-9/_-]*\d[A-Z0-9/_-]*\b",
    re.IGNORECASE,
)
_CONFIDENCE_THRESHOLD = 0.5


def _extract_ref_tokens(text: str) -> set[str]:
    return {token.casefold() for token in _REF_TOKEN_RE.findall(text)}


@dataclass
class A4Result:
    total_profiles: int
    profiles_reidentified: int

    @property
    def reidentification_rate(self) -> float:
        return self.profiles_reidentified / self.total_profiles if self.total_profiles else 0.0


def _profile_confidence(pooled_text: str, registry: list[RegistryPerson]) -> float:
    ages = extract_age_candidates(pooled_text)
    pins = extract_pins(pooled_text)
    candidates = []
    for person in registry:
        if ages and person.age is not None and not any(abs(person.age - age) <= 2 for age in ages):
            continue
        if pins and person.pin and person.pin not in pins:
            continue
        candidates.append(person)
    if not candidates:
        return 0.0
    scores = [_candidate_score(pooled_text.casefold(), person) for person in candidates]
    total = sum(scores) or 1.0
    top = max(scores)
    return top / total if top > 0 else 0.0


def _connected_profiles(records: list[ReleaseRecord]) -> list[list[ReleaseRecord]]:
    parent = list(range(len(records)))

    def find(index: int) -> int:
        root = index
        while parent[root] != root:
            root = parent[root]
        while parent[index] != index:
            next_index = parent[index]
            parent[index] = root
            index = next_index
        return root

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left == root_right:
            return
        if root_right < root_left:
            root_left, root_right = root_right, root_left
        parent[root_right] = root_left

    first_by_pseudonym: dict[str, int] = {}
    first_by_reference: dict[str, int] = {}
    for index, record in enumerate(records):
        if record.pseudonym:
            previous = first_by_pseudonym.setdefault(record.pseudonym, index)
            union(previous, index)
        for token in sorted(_extract_ref_tokens(record.text)):
            previous = first_by_reference.setdefault(token, index)
            union(previous, index)

    groups: dict[int, list[ReleaseRecord]] = {}
    for index, record in enumerate(records):
        groups.setdefault(find(index), []).append(record)
    return [groups[root] for root in sorted(groups)]


def run_a4(records: list[ReleaseRecord], registry: list[RegistryPerson]) -> A4Result:
    profiles = _connected_profiles(records)
    reidentified = 0
    for profile_records in profiles:
        pooled_text = " ".join(record.text for record in profile_records)
        confidence = max(
            _profile_confidence(pooled_text, registry),
            max(
                (_profile_confidence(record.text, registry) for record in profile_records),
                default=0.0,
            ),
        )
        if confidence >= _CONFIDENCE_THRESHOLD:
            reidentified += 1
    return A4Result(total_profiles=len(profiles), profiles_reidentified=reidentified)
