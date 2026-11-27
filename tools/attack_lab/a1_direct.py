"""A1: direct exposure.

Any surviving full name or direct identifier from the registry/known-facts files, found
anywhere in the release text, exposes that person. This is the cheapest, strongest
attack and should be driven to zero before anything else matters.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .common import ReleaseRecord, RegistryPerson

# docs/ATTACKS.md: the attacker extracts "masked phones (98XXXXXX10), masked Aadhaar
# (XXXX XXXX 1234)" -- a last-4 digit exposure means the last 4 digits appear in that
# masked DISPLAY form, not a bare 4-digit substring floating anywhere in the release.
# A bare substring search matches constantly by coincidence (a UUID, a lab value, any
# unrelated number) because 4 digits recur often across hundreds of records; it is not
# a real identifier leak and the real evaluator's own extraction rule does not read it
# that way either. Mirrors tools/attack_lab/a3_linkage.py's _MASKED_AADHAAR_RE.
_MASKED_AADHAAR_RE = re.compile(r"(?:X[\s-]*){8}(\d{4})", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?([6-9]\d{4}[\s-]?\d{5})(?!\d)")


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
    masked_aadhaar_last4 = set(_MASKED_AADHAAR_RE.findall(full_text))
    full_phones = {
        re.sub(r"\D", "", match)[-10:] for match in _PHONE_RE.findall(full_text)
    }
    exposed = set()
    for person in registry:
        name = person.name.strip().lower()
        if name and len(name) > 3 and name in full_text:
            exposed.add(person.rid)
            continue
        if person.aadhaar_last4 and person.aadhaar_last4 in masked_aadhaar_last4:
            exposed.add(person.rid)
            continue
        if person.phone and person.phone in full_phones:
            exposed.add(person.rid)
    return A1Result(exposed_rids=exposed, total_people=len(registry))
