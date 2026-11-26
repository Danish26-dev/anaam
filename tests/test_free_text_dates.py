"""Regression tests: free-text dates embedded in non-date-typed fields must still be
shifted by the record's offset, not just dates in recognized date columns/keys.

This is the exact gap the README previously documented as a known limitation: a date
mentioned inside a CSV "Notes" cell, or an ordinary JSON string value, used to pass
through untouched because render_text() was called without the row/record offset.
"""
from __future__ import annotations

import json
import unittest

import tests.conftest_path  # noqa: F401

from export.csv_writer import render_csv
from export.fhir_writer import render_fhir_bundle
from export.json_writer import render_json_doc
from ingest.fhir_adapter import index_bundle


class CsvFreeTextDateShiftTests(unittest.TestCase):
    def test_date_inside_a_non_date_column_is_shifted(self):
        header = ["Name", "Notes"]
        rows = [["Ravi Kumar", "Admitted on 04/02/2026, discharged a week later."]]
        text, _ = render_csv(header, rows, ",", {0: None}, {0: 10})
        self.assertIn("14/02/2026", text)
        self.assertNotIn("04/02/2026", text)

    def test_recognized_date_column_is_not_double_shifted(self):
        header = ["Name", "Reg Date"]
        rows = [["Ravi Kumar", "04/02/2026"]]
        text, _ = render_csv(header, rows, ",", {0: None}, {0: 10})
        # Only one occurrence of the shifted date; the free-text fallback must not also
        # re-shift a cell that already went through the recognized-date-column path.
        self.assertEqual(text.count("14/02/2026"), 1)


class JsonFreeTextDateShiftTests(unittest.TestCase):
    def test_date_inside_an_ordinary_string_value_is_shifted(self):
        data = {"notes": "Follow-up scheduled for 04/02/2026."}
        text, _ = render_json_doc(data, date_offset_days=10)
        parsed = json.loads(text)
        self.assertIn("14/02/2026", parsed["notes"])


class FhirNarrativeFreeTextDateShiftTests(unittest.TestCase):
    def test_date_inside_narrative_text_div_is_shifted(self):
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "fullUrl": "urn:uuid:patient-1",
                    "resource": {"resourceType": "Patient", "id": "old-id"},
                },
                {
                    "resource": {
                        "resourceType": "Composition",
                        "text": {"div": "<div>Visited on 04/02/2026 for review.</div>"},
                        "subject": {"reference": "urn:uuid:patient-1"},
                    },
                },
            ],
        }
        index = index_bundle(bundle)
        text, _ = render_fhir_bundle(bundle, index, "PSN-ABC", date_offset_days=10)
        self.assertIn("14/02/2026", text)
        self.assertNotIn("04/02/2026", text)


if __name__ == "__main__":
    unittest.main()
