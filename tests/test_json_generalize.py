"""Regression tests for O10 JSON generalization (src/privacy/json_generalize.py)."""
from __future__ import annotations

import unittest

import tests.conftest_path  # noqa: F401

from privacy.generalize import VillageHierarchy
from privacy.json_generalize import (
    collect_village_hierarchy_facts,
    find_village_and_district,
    generalize_json_record,
)
from privacy.profile_policy import ProfilePrivacyPlan


class FindVillageAndDistrictTests(unittest.TestCase):
    def test_finds_nested_village_and_district(self):
        record = {
            "age": 51,
            "address": {"village": "Tilakpura", "tehsil": "Bilgram", "district": "Hardoi", "pin": "248117"},
        }
        village, district = find_village_and_district(record)
        self.assertEqual(village, "Tilakpura")
        self.assertEqual(district, "Hardoi")

    def test_returns_none_when_absent(self):
        village, district = find_village_and_district({"age": 30})
        self.assertIsNone(village)
        self.assertIsNone(district)


class CollectVillageHierarchyFactsTests(unittest.TestCase):
    def test_collects_facts_from_a_list_of_records(self):
        data = {
            "patients": [
                {"address": {"village": "Tilakpura", "tehsil": "Bilgram", "district": "Hardoi"}},
                {"address": {"village": "Sonbarsa", "district": "Sitapur"}},
            ]
        }
        facts = collect_village_hierarchy_facts(data)
        self.assertIn(("Tilakpura", "Bilgram", "Hardoi"), facts)
        self.assertIn(("Sonbarsa", None, "Sitapur"), facts)


class GeneralizeJsonRecordTests(unittest.TestCase):
    def test_age_is_banded_and_contains_true_value(self):
        plan = ProfilePrivacyPlan(pseudonym="p1", age_band_years=5, village_level="tehsil", pin_keep_digits=3)
        record = {"age": 51}
        generalized, transformations = generalize_json_record(record, plan, VillageHierarchy())
        self.assertEqual(generalized["age"], "50-54")
        self.assertEqual(len(transformations), 1)
        self.assertEqual(transformations[0].action, "generalize")

    def test_age_as_numeric_string_is_also_banded(self):
        plan = ProfilePrivacyPlan(pseudonym="p1", age_band_years=5, village_level="tehsil", pin_keep_digits=3)
        record = {"age": "51"}
        generalized, _ = generalize_json_record(record, plan, VillageHierarchy())
        self.assertEqual(generalized["age"], "50-54")

    def test_bool_value_under_age_key_is_never_treated_as_age(self):
        """bool is an int subclass in Python; must not silently band True/False."""
        plan = ProfilePrivacyPlan(pseudonym="p1", age_band_years=5, village_level="tehsil", pin_keep_digits=3)
        record = {"age": True}
        generalized, transformations = generalize_json_record(record, plan, VillageHierarchy())
        self.assertIs(generalized["age"], True)
        self.assertEqual(transformations, [])

    def test_village_is_generalized_to_tehsil_when_mapping_known(self):
        hierarchy = VillageHierarchy()
        hierarchy.learn("Tilakpura", "Bilgram", "Hardoi")
        plan = ProfilePrivacyPlan(pseudonym="p1", age_band_years=5, village_level="tehsil", pin_keep_digits=3)
        record = {"address": {"village": "Tilakpura"}}
        generalized, transformations = generalize_json_record(record, plan, hierarchy)
        self.assertEqual(generalized["address"]["village"], "Bilgram")
        self.assertEqual(transformations[0].path, "address/village")

    def test_village_suppresses_to_empty_when_no_mapping_known(self):
        plan = ProfilePrivacyPlan(pseudonym="p1", age_band_years=5, village_level="tehsil", pin_keep_digits=3)
        record = {"address": {"village": "UnknownVillage"}}
        generalized, transformations = generalize_json_record(record, plan, VillageHierarchy())
        self.assertEqual(generalized["address"]["village"], "")
        self.assertEqual(transformations[0].action, "suppress")

    def test_pin_is_truncated_to_prefix(self):
        plan = ProfilePrivacyPlan(pseudonym="p1", age_band_years=5, village_level="tehsil", pin_keep_digits=3)
        record = {"address": {"pin": "248117"}}
        generalized, transformations = generalize_json_record(record, plan, VillageHierarchy())
        self.assertEqual(generalized["address"]["pin"], "248")
        self.assertEqual(transformations[0].action, "generalize")

    def test_suppress_level_blanks_village_tehsil_district_and_pin(self):
        plan = ProfilePrivacyPlan(pseudonym="p1", age_band_years=5, village_level="suppress", pin_keep_digits=3)
        hierarchy = VillageHierarchy()
        hierarchy.learn("Tilakpura", "Bilgram", "Hardoi")
        record = {"address": {"village": "Tilakpura", "tehsil": "Bilgram", "district": "Hardoi", "pin": "248117"}}
        generalized, _ = generalize_json_record(record, plan, hierarchy)
        self.assertEqual(generalized["address"]["village"], "")
        self.assertEqual(generalized["address"]["tehsil"], "")
        self.assertEqual(generalized["address"]["district"], "")
        self.assertEqual(generalized["address"]["pin"], "")

    def test_original_record_is_not_mutated(self):
        plan = ProfilePrivacyPlan(pseudonym="p1", age_band_years=5, village_level="tehsil", pin_keep_digits=3)
        record = {"age": 51, "address": {"pin": "248117"}}
        generalize_json_record(record, plan, VillageHierarchy())
        self.assertEqual(record["age"], 51)
        self.assertEqual(record["address"]["pin"], "248117")

    def test_non_quasi_identifier_fields_pass_through_unchanged(self):
        plan = ProfilePrivacyPlan(pseudonym="p1", age_band_years=5, village_level="tehsil", pin_keep_digits=3)
        record = {"diagnosis": "Type 2 diabetes mellitus", "age": 51}
        generalized, _ = generalize_json_record(record, plan, VillageHierarchy())
        self.assertEqual(generalized["diagnosis"], "Type 2 diabetes mellitus")

    def test_records_inside_a_list_are_each_generalized(self):
        plan = ProfilePrivacyPlan(pseudonym="p1", age_band_years=5, village_level="tehsil", pin_keep_digits=3)
        record = {"visits": [{"age": 10}, {"age": 60}]}
        generalized, transformations = generalize_json_record(record, plan, VillageHierarchy())
        self.assertEqual(generalized["visits"][0]["age"], "10-14")
        self.assertEqual(generalized["visits"][1]["age"], "60-64")
        self.assertEqual(len(transformations), 2)


if __name__ == "__main__":
    unittest.main()
