"""A5: local known-facts attack and global-shift recovery probe."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .a3_linkage import record_linkage
from .common import KnownFact, RegistryPerson, ReleaseRecord, extract_dates_iso


@dataclass
class A5Result:
    found_known_facts: int
    total_known_facts: int
    global_shift_recoverable: bool
    recovered_offset_days: int | None

    @property
    def targeted_success_rate(self) -> float:
        return self.found_known_facts / self.total_known_facts if self.total_known_facts else 0.0


def _profiles(records: list[ReleaseRecord]) -> dict[str, list[ReleaseRecord]]:
    profiles: dict[str, list[ReleaseRecord]] = {}
    for index, record in enumerate(records):
        if record.pseudonym:
            key = f"patient:{record.pseudonym}"
        else:
            key = f"unlinked:{record.source_key or index}:{record.loc or index}"
        profiles.setdefault(key, []).append(record)
    return profiles


def _stay_lengths(records: list[ReleaseRecord]) -> set[int]:
    lengths: set[int] = set()
    for record in records:
        parsed: list[dt.date] = []
        for value in extract_dates_iso(record.text):
            try:
                parsed.append(dt.date.fromisoformat(value))
            except ValueError:
                continue
        parsed.sort()
        for left_index, left in enumerate(parsed):
            for right in parsed[left_index + 1:]:
                lengths.add((right - left).days)
    return lengths


def run_a5(
    records: list[ReleaseRecord],
    known_facts: list[KnownFact],
    registry: list[RegistryPerson] | None = None,
) -> A5Result:
    profiles = _profiles(records)
    profile_data = {}
    for key, profile_records in profiles.items():
        pooled_text = " ".join(record.text for record in profile_records)
        linked_rid, linkage_confidence = (
            record_linkage(ReleaseRecord(pseudonym=None, text=pooled_text), registry)
            if registry else (None, 0.0)
        )
        profile_data[key] = {
            "records": profile_records,
            "text": pooled_text.casefold(),
            "dates": set().union(
                *(extract_dates_iso(record.text) for record in profile_records)
            ) if profile_records else set(),
            "stay_lengths": _stay_lengths(profile_records),
            "linked_rid": linked_rid,
            "linkage_confidence": linkage_confidence,
        }

    found = 0
    # One offset needs support from at least two distinct known people, not merely two
    # date combinations from the same profile.
    offset_supporters: dict[int, set[str]] = {}

    for fact in known_facts:
        fact_found = False
        for data in profile_data.values():
            text = data["text"]
            dates = data["dates"]
            hospital_match = not fact.hospital or fact.hospital.casefold() in text
            date_match = any(date in dates for date in fact.visit_dates)
            condition_match = bool(
                fact.condition_hint and fact.condition_hint.casefold() in text
            )
            stay_match = bool(
                fact.length_of_stay_days is not None
                and fact.length_of_stay_days in data["stay_lengths"]
            )

            high_confidence_rid = (
                data["linked_rid"] if data["linkage_confidence"] >= 0.9 else None
            )
            profile_consistent = high_confidence_rid in (None, fact.rid)

            # Hospital is supporting evidence, never a targeted fact by itself.
            if profile_consistent and hospital_match and (date_match or condition_match or stay_match):
                fact_found = True

            # Mirror the documented global-shift recovery precondition: only profiles
            # already re-identified with >=0.9 confidence can vote for an offset.
            if high_confidence_rid == fact.rid and hospital_match:
                for true_date_string in fact.visit_dates:
                    try:
                        true_date = dt.date.fromisoformat(true_date_string)
                    except ValueError:
                        continue
                    for release_date_string in dates:
                        try:
                            release_date = dt.date.fromisoformat(release_date_string)
                        except ValueError:
                            continue
                        offset = (release_date - true_date).days
                        offset_supporters.setdefault(offset, set()).add(fact.rid)

        if fact_found:
            found += 1

    recovered_offset = None
    if offset_supporters:
        best_offset, supporters = max(
            offset_supporters.items(), key=lambda item: (len(item[1]), -abs(item[0]), item[0])
        )
        if len(supporters) >= 2:
            recovered_offset = best_offset

    return A5Result(
        found_known_facts=found,
        total_known_facts=len(known_facts),
        global_shift_recoverable=recovered_offset is not None,
        recovered_offset_days=recovered_offset,
    )
