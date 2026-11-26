"""O10: profile-consistent generalization policy.

Important policy rule from the plan: "A profile receives one compatible privacy plan. One
record cannot retain an exact village while another record for the same pseudonym uses
only a district." This module enforces that by computing ONE generalization level per
patient profile (pseudonym) up front, then applying it uniformly to every record in that
profile, rather than letting each record decide its own level independently.
"""
from __future__ import annotations

from dataclasses import dataclass

from .generalize import VillageHierarchy, age_band, is_rare_combination, pin_to_prefix


@dataclass
class ProfilePrivacyPlan:
    pseudonym: str
    age_band_years: int
    village_level: str  # "tehsil" | "district" | "suppress"
    pin_keep_digits: int
    suppress_record: bool = False


def decide_profile_plan(
    pseudonym: str,
    group_size_by_village: dict[str, int],
    village: str | None,
    min_group_size: int,
    age_band_years: int,
    group_size_by_district: dict[str, int] | None = None,
    district: str | None = None,
) -> ProfilePrivacyPlan:
    """One plan per profile, escalating through three levels before giving up truthful
    generalization and suppressing instead (suppression is the LAST resort, per O10):

      1. village-level group is large enough (>= min_group_size): keep tehsil detail.
      2. village-level group is rare: widen to district.
      3. even the DISTRICT-level group is rare (a thin, mostly-empty district for this
         age band): there is no coarser truthful level left for this quasi-identifier
         short of dropping it, so the plan marks village_level="suppress". This is what
         protects the "97-year-old with a rare procedure" re-identification trap, where
         even "district + wide age band" can still be a group of one.
    """
    village_key = (village or "").strip().lower()
    district_key = (district or "").strip().lower()
    village_group_size = group_size_by_village.get(village_key, 0)

    village_level = "tehsil"
    if village and is_rare_combination(village_group_size, min_group_size):
        village_level = "district"
        if group_size_by_district is not None:
            district_group_size = group_size_by_district.get(district_key, 0)
            if district and is_rare_combination(district_group_size, min_group_size):
                village_level = "suppress"

    return ProfilePrivacyPlan(
        pseudonym=pseudonym,
        age_band_years=age_band_years,
        village_level=village_level,
        pin_keep_digits=3,
    )


def apply_plan_to_age(plan: ProfilePrivacyPlan, true_age: int) -> str:
    return age_band(true_age, band_years=plan.age_band_years)


def apply_plan_to_village(plan: ProfilePrivacyPlan, village: str, hierarchy: VillageHierarchy) -> str | None:
    if plan.village_level == "suppress":
        return None
    return hierarchy.generalize(village, level=plan.village_level)


def apply_plan_to_pin(plan: ProfilePrivacyPlan, pin: str) -> str:
    if plan.village_level == "suppress":
        # When even the district-level quasi-identifier group is rare, a PIN prefix
        # (which maps back toward a small area) is dropped too rather than left as a
        # weaker-but-still-identifying residual signal.
        return ""
    return pin_to_prefix(pin, keep_digits=plan.pin_keep_digits)
