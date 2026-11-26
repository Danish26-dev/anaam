"""A1: direct exposure.

Any surviving full name or direct identifier from the registry/known-facts files, found
anywhere in the release text, exposes that person. This is the cheapest, strongest
attack and should be driven to zero before anything else matters.
"""
from __future__ import annotations

from dataclasses import dataclass

from .common import ReleaseRecord, RegistryPerson


@dataclass
class A1Result:
    exposed_rids: set[str]
    total_people: int

    @property
    def exposure_rate(self) -> float:
        return len(self.exposed_rids) / self.total_people if self.total_people else 0.0


def run_a1(records: list[ReleaseRecord], registry: list[RegistryPerson]) -> A1Result:
    # Output filenames are attacker-visible side channels and are scanned alongside content.
    full_text = "\n".join(
        f"{record.file or ''}\n{record.text}" for record in records
    ).lower()
    exposed = set()
    for person in registry:
        name = person.name.strip().lower()
        if name and len(name) > 3 and name in full_text:
            exposed.add(person.rid)
            continue
        if person.aadhaar_last4 and person.aadhaar_last4 in full_text:
            exposed.add(person.rid)
            continue
        if person.phone and person.phone in full_text:
            exposed.add(person.rid)
    return A1Result(exposed_rids=exposed, total_people=len(registry))
