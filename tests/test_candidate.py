"""Regression tests for in-memory candidate staging and atomic publication."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import tests.conftest_path  # noqa: F401

from export.candidate import (
    publish_candidates,
    text_candidate,
    validate_candidate_structures,
)


class PublishCandidatesTests(unittest.TestCase):
    def test_publishes_all_files_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            sanitized_dir = Path(tmp) / "out" / "sanitized"
            candidates = [
                text_candidate("a/one.txt", "hello", "text"),
                text_candidate("b/two.json", "{}", "json"),
            ]
            publish_candidates(sanitized_dir, candidates)
            self.assertEqual((sanitized_dir / "a" / "one.txt").read_text(), "hello")
            self.assertEqual((sanitized_dir / "b" / "two.json").read_text(), "{}")
            # No leftover staging directory after a successful publish.
            self.assertFalse((sanitized_dir.parent / ".anaam-candidate-staging").exists())

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            sanitized_dir = Path(tmp) / "out" / "sanitized"
            candidates = [text_candidate("../escape.txt", "x", "text")]
            with self.assertRaises(ValueError):
                publish_candidates(sanitized_dir, candidates)
            # Nothing should have been written outside the staging area at all.
            self.assertFalse(sanitized_dir.exists())

    def test_rejects_duplicate_output_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            sanitized_dir = Path(tmp) / "out" / "sanitized"
            candidates = [
                text_candidate("a.txt", "one", "text"),
                text_candidate("a.txt", "two", "text"),
            ]
            with self.assertRaises(ValueError):
                publish_candidates(sanitized_dir, candidates)

    def test_refuses_to_publish_into_existing_sanitized_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            sanitized_dir = Path(tmp) / "out" / "sanitized"
            sanitized_dir.mkdir(parents=True)
            with self.assertRaises(ValueError):
                publish_candidates(sanitized_dir, [text_candidate("a.txt", "x", "text")])


class ValidateCandidateStructuresTests(unittest.TestCase):
    def test_valid_csv_and_json_pass(self):
        validate_candidate_structures([
            text_candidate("a.csv", "x,y\n1,2\n", "csv"),
            text_candidate("b.json", json.dumps({"x": 1}), "json"),
        ])  # no exception raised

    def test_invalid_json_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_candidate_structures([text_candidate("b.json", "{not valid", "json")])

    def test_fhir_bundle_must_have_resource_type_bundle(self):
        with self.assertRaises(ValueError):
            validate_candidate_structures(
                [text_candidate("f.json", json.dumps({"resourceType": "Patient"}), "fhir")]
            )

    def test_fhir_unresolved_patient_reference_is_rejected(self):
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "fullUrl": "urn:uuid:abc",
                    "resource": {
                        "resourceType": "Observation",
                        "subject": {"reference": "Patient/does-not-exist"},
                    },
                },
            ],
        }
        with self.assertRaises(ValueError):
            validate_candidate_structures([text_candidate("f.json", json.dumps(bundle), "fhir")])

    def test_fhir_resolvable_reference_passes(self):
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {"fullUrl": "urn:uuid:p1", "resource": {"resourceType": "Patient", "id": "PSN-ABC"}},
                {
                    "resource": {
                        "resourceType": "Observation",
                        "subject": {"reference": "Patient/PSN-ABC"},
                    },
                },
            ],
        }
        validate_candidate_structures([text_candidate("f.json", json.dumps(bundle), "fhir")])


if __name__ == "__main__":
    unittest.main()
