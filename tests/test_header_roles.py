"""Regression tests for the shared header-role table (core.header_roles).

Covers the exact gap found during the audit: a renamed PIN-equivalent header ("Zip")
being silently skipped because it was missing from one of three previously-duplicated
literal sets.
"""
from __future__ import annotations

import unittest

import tests.conftest_path  # noqa: F401

from core.header_roles import (
    declared_date_hint,
    find_column,
    find_patient_identity_column,
    normalize_header,
    role_for_header,
)


class RoleForHeaderTests(unittest.TestCase):
    def test_exact_known_headers(self):
        self.assertEqual(role_for_header("Age"), "age")
        self.assertEqual(role_for_header("Village/Mohalla"), "village")
        self.assertEqual(role_for_header("Tehsil"), "tehsil")
        self.assertEqual(role_for_header("District"), "district")
        self.assertEqual(role_for_header("PIN"), "pin")

    def test_renamed_pin_equivalent_headers_are_recognized(self):
        # This is the exact case the practice dataset's legacy export CSV uses.
        self.assertEqual(role_for_header("Zip"), "pin")
        self.assertEqual(role_for_header("Postal Code"), "pin")
        self.assertEqual(role_for_header("Pincode"), "pin")

    def test_underscore_and_hyphen_variants_normalize_the_same(self):
        self.assertEqual(role_for_header("admission_date"), "date")
        self.assertEqual(role_for_header("admission-date"), "date")
        self.assertEqual(role_for_header("Admission Date"), "date")

    def test_declared_date_format_suffix_is_stripped_before_role_lookup(self):
        self.assertEqual(role_for_header("DOB (MM/DD/YYYY)"), "date")

    def test_unrecognized_header_returns_none(self):
        self.assertIsNone(role_for_header("some_unrelated_column"))

    def test_normalize_header_collapses_whitespace_and_separators(self):
        self.assertEqual(normalize_header("Patient_Name"), "patient name")
        self.assertEqual(normalize_header("patient-name"), "patient name")
        self.assertEqual(normalize_header("  Patient   Name  "), "patient name")


class DeclaredDateHintTests(unittest.TestCase):
    def test_mdy_declared_format(self):
        self.assertEqual(declared_date_hint("DOB (MM/DD/YYYY)"), "mdy")

    def test_dmy_declared_format(self):
        self.assertEqual(declared_date_hint("Reg Date (DD/MM/YYYY)"), "dmy")

    def test_no_declared_format_returns_none(self):
        self.assertIsNone(declared_date_hint("DOB"))


class FindColumnTests(unittest.TestCase):
    def test_finds_correct_index_among_many_columns(self):
        header = ["PatientID", "LastName", "FirstName", "Sex", "Zip", "Phone"]
        self.assertEqual(find_column(header, "pin"), 4)

    def test_returns_none_when_role_absent(self):
        header = ["a", "b", "c"]
        self.assertIsNone(find_column(header, "pin"))


class FindPatientIdentityColumnTests(unittest.TestCase):
    def test_prefers_stronger_identifier_over_bare_name(self):
        header = ["Name", "UHID", "Age"]
        # UHID should win even though "Name" appears first, because
        # PATIENT_IDENTITY_HEADERS is checked in priority order, not left-to-right.
        self.assertEqual(find_patient_identity_column(header), 1)

    def test_falls_back_to_bare_name_when_no_scoped_id_present(self):
        header = ["Age", "Name", "Gender"]
        self.assertEqual(find_patient_identity_column(header), 1)

    def test_returns_none_when_no_identity_column_exists(self):
        header = ["drug", "strength", "form"]
        self.assertIsNone(find_patient_identity_column(header))


if __name__ == "__main__":
    unittest.main()
