"""Regression tests for src/ingest/fhir_adapter.py's Bundle indexing."""
from __future__ import annotations

import unittest

import tests.conftest_path  # noqa: F401

from ingest.fhir_adapter import index_bundle


class NarrativePointerTests(unittest.TestCase):
    def test_text_div_narrative_is_indexed_exactly_once(self):
        """A `text: {div: ...}` block must not be recorded twice -- once when the walk
        visits the Composition/Patient resource itself, and again when it recurses into
        that same resource's `text` child and sees a bare `div` key there.
        """
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Composition",
                        "text": {"div": "<div>Some narrative.</div>"},
                    },
                },
            ],
        }
        index = index_bundle(bundle)
        self.assertEqual(index.narrative_pointers, ["/entry/0/resource/text/div"])

    def test_multiple_distinct_narratives_are_all_indexed(self):
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {"resource": {"resourceType": "Composition", "text": {"div": "first"}}},
                {"resource": {"resourceType": "Patient", "text": {"div": "second"}}},
            ],
        }
        index = index_bundle(bundle)
        self.assertEqual(
            sorted(index.narrative_pointers),
            ["/entry/0/resource/text/div", "/entry/1/resource/text/div"],
        )

    def test_no_narrative_present_yields_empty_list(self):
        bundle = {"resourceType": "Bundle", "entry": [{"resource": {"resourceType": "Observation"}}]}
        index = index_bundle(bundle)
        self.assertEqual(index.narrative_pointers, [])


if __name__ == "__main__":
    unittest.main()
