"""O10: static privacy policy -- quasi-identifier generalization.

Pure functions, each truthful by construction (the output band/region always contains
the true value), so Danish's independent verifier can check "band contains true age"
without trusting how the band was produced.
"""
from __future__ import annotations

TOP_CODE_AGE = 90  # ages at/above this collapse to a single open-ended band


def age_band(age: int, band_years: int = 5, top_code: int = TOP_CODE_AGE) -> str:
    """5-year band by default. Ages >= top_code collapse to "<top_code>+" (old-age
    top-coding), since very old ages are rare enough to be identifying on their own.
    """
    if age < 0:
        raise ValueError("age_negative")
    if age >= top_code:
        return f"{top_code}+"
    lo = (age // band_years) * band_years
    hi = lo + band_years - 1
    return f"{lo}-{hi}"


def pin_to_prefix(pin: str, keep_digits: int = 3) -> str:
    """Reduce a 6-digit PIN to its leading digits (region-level), e.g. "110092" -> "110"."""
    digits = "".join(ch for ch in pin if ch.isdigit())
    return digits[:keep_digits] if digits else ""


class VillageHierarchy:
    """Maps a village name to its tehsil/district using a lookup table built from the
    input data itself (registration rows that have Village + Tehsil + District together).
    Falls back to "unknown" rather than guessing, which forces suppression downstream
    instead of a silently wrong generalization.
    """

    def __init__(self):
        self._village_to_tehsil: dict[str, str] = {}
        self._village_to_district: dict[str, str] = {}

    def learn(self, village: str, tehsil: str | None, district: str | None) -> None:
        key = village.strip().lower()
        if not key:
            return
        if tehsil:
            self._village_to_tehsil.setdefault(key, tehsil)
        if district:
            self._village_to_district.setdefault(key, district)

    def tehsil_for(self, village: str) -> str | None:
        return self._village_to_tehsil.get(village.strip().lower())

    def district_for(self, village: str) -> str | None:
        return self._village_to_district.get(village.strip().lower())

    def generalize(self, village: str, level: str = "district") -> str | None:
        if level == "tehsil":
            return self.tehsil_for(village)
        return self.district_for(village)


def is_rare_combination(group_size: int, min_group_size: int) -> bool:
    """True when a quasi-identifier combination (e.g. village+age-band+gender+diagnosis)
    is rarer than the configured k-anonymity threshold and should be suppressed or
    further generalized rather than released as-is.
    """
    return group_size < min_group_size
