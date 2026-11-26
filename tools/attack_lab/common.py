"""Shared helpers for the local attacker simulator (O11).

IMPORTANT: this whole tools/attack_lab package is a DEVELOPMENT TOOL. It reads
dev/attacker/registry.csv and dev/attacker/known_facts.jsonl, which only exist in the
practice kit -- the real evaluator's attacker and its registry are never available to a
submission at runtime. Nothing in this package may be imported by main.py or by anything
that runs during `run`. It exists purely so Omkar can measure local privacy risk before
submitting, mirroring (not literally reusing) the documented attack methodology in
docs/ATTACKS.md.

These are LOCAL measurements, not the official score -- the real evaluator uses a hidden
registry built from a different, unseen dataset.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RegistryPerson:
    rid: str
    name: str
    relation: str
    relative_name: str
    gender: str
    age: int | None
    house_no: str
    mohalla: str
    village: str
    tehsil: str
    district: str
    pin: str
    phone: str
    email: str
    aadhaar_last4: str


def load_registry(path: Path) -> list[RegistryPerson]:
    people = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            age = None
            if row.get("age", "").strip().isdigit():
                age = int(row["age"])
            people.append(
                RegistryPerson(
                    rid=row["rid"],
                    name=row["name"],
                    relation=row.get("relation", ""),
                    relative_name=row.get("relative_name", ""),
                    gender=row.get("gender", ""),
                    age=age,
                    house_no=row.get("house_no", ""),
                    mohalla=row.get("mohalla", ""),
                    village=row.get("village", ""),
                    tehsil=row.get("tehsil", ""),
                    district=row.get("district", ""),
                    pin=row.get("pin", ""),
                    phone=row.get("phone", ""),
                    email=row.get("email", ""),
                    aadhaar_last4=row.get("aadhaar_last4", ""),
                )
            )
    return people


@dataclass
class KnownFact:
    rid: str
    visit_dates: list[str]
    hospital: str | None = None
    condition_hint: str | None = None
    length_of_stay_days: int | None = None


def load_known_facts(path: Path) -> list[KnownFact]:
    facts = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            facts.append(
                KnownFact(
                    rid=d["rid"],
                    visit_dates=d.get("visit_dates", []),
                    hospital=d.get("hospital"),
                    condition_hint=d.get("condition_hint"),
                    length_of_stay_days=d.get("stay_days", d.get("length_of_stay_days")),
                )
            )
    return facts


@dataclass
class ReleaseRecord:
    """One sanitized record as seen by the local attacker."""

    pseudonym: str | None
    text: str
    source_key: str | None = None  # input SHA + duplicate occurrence from report.json
    file: str | None = None
    loc: str | None = None


_DATE_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DATE_DMY_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2}(?:\d{2})?)\b")
_AGE_RE = re.compile(r"\b(\d{1,3})\s*(?:Y|Yrs?|yrs?|वर्ष)\b", re.IGNORECASE)
_AGE_BAND_RE = re.compile(r"\b(\d{1,3})\s*-\s*(\d{1,3})\b")
_GENDER_RE = re.compile(r"\b([MF])\b")
_PIN_RE = re.compile(r"\b(\d{6})\b")


def extract_dates_iso(text: str) -> set[str]:
    out = set()
    for y, m, d in _DATE_ISO_RE.findall(text):
        out.add(f"{y}-{m}-{d}")
    for day, month, year_text in _DATE_DMY_RE.findall(text):
        year_value = int(year_text)
        year = (
            2000 + year_value if len(year_text) == 2 and year_value < 70
            else 1900 + year_value if len(year_text) == 2
            else year_value
        )
        out.add(f"{year:04d}-{int(month):02d}-{int(day):02d}")
    return out


def extract_age_candidates(text: str) -> set[int]:
    out = set()
    for m in _AGE_RE.finditer(text):
        out.add(int(m.group(1)))
    for lo, hi in _AGE_BAND_RE.findall(text):
        lo_i, hi_i = int(lo), int(hi)
        if 0 <= lo_i <= 120 and 0 <= hi_i <= 120 and hi_i - lo_i <= 10:
            out.update(range(lo_i, hi_i + 1))
    return out


def extract_pins(text: str) -> set[str]:
    return set(_PIN_RE.findall(text))


def group_records_by_pseudonym(records: list[ReleaseRecord]) -> dict[str, list[ReleaseRecord]]:
    groups: dict[str, list[ReleaseRecord]] = {}
    for r in records:
        if r.pseudonym:
            groups.setdefault(r.pseudonym, []).append(r)
    return groups
