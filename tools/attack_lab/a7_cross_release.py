"""A7: cross-release linkability keyed by stable input-record identity."""
from __future__ import annotations

from dataclasses import dataclass

from .common import ReleaseRecord, extract_dates_iso


@dataclass
class A7Result:
    total_record_pairs_compared: int
    stable_pseudonym_pairs: int
    stable_date_pairs: int
    unmatched_records: int = 0

    @property
    def pseudonym_stability_rate(self) -> float:
        return (
            self.stable_pseudonym_pairs / self.total_record_pairs_compared
            if self.total_record_pairs_compared else 0.0
        )

    @property
    def date_stability_rate(self) -> float:
        return (
            self.stable_date_pairs / self.total_record_pairs_compared
            if self.total_record_pairs_compared else 0.0
        )

    @property
    def risk(self) -> float:
        return max(self.pseudonym_stability_rate, self.date_stability_rate)


def _keyed(records: list[ReleaseRecord]) -> dict[tuple[str, str], ReleaseRecord]:
    keyed: dict[tuple[str, str], ReleaseRecord] = {}
    for index, record in enumerate(records):
        source_key = record.source_key or f"position:{index}"
        locator = record.loc or f"record:{index}"
        keyed[(source_key, locator)] = record
    return keyed


def run_a7(release_a: list[ReleaseRecord], release_b: list[ReleaseRecord]) -> A7Result:
    records_a, records_b = _keyed(release_a), _keyed(release_b)
    common_keys = sorted(set(records_a) & set(records_b))
    unmatched = len(set(records_a) ^ set(records_b))

    stable_pseudonym = 0
    stable_date = 0
    for key in common_keys:
        record_a, record_b = records_a[key], records_b[key]
        if (
            record_a.pseudonym
            and record_b.pseudonym
            and record_a.pseudonym == record_b.pseudonym
        ):
            stable_pseudonym += 1
        dates_a = extract_dates_iso(record_a.text)
        dates_b = extract_dates_iso(record_b.text)
        if dates_a and dates_b and dates_a & dates_b:
            stable_date += 1

    return A7Result(
        total_record_pairs_compared=len(common_keys),
        stable_pseudonym_pairs=stable_pseudonym,
        stable_date_pairs=stable_date,
        unmatched_records=unmatched,
    )
