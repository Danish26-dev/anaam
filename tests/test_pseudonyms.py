"""O8 regression tests: pseudonym stability, secret-sensitivity, collision handling."""
from __future__ import annotations

import unittest

import tests.conftest_path  # noqa: F401

from core.interfaces import ClusterAssignment
from core.record_ids import make_record_id
from privacy.pseudonyms import build_pseudonym_map, pseudonym_for_cluster


class PseudonymFingerprintTests(unittest.TestCase):
    def test_same_members_different_order_same_pseudonym(self):
        key = b"k" * 32
        members = ["r1", "r2", "r3"]
        self.assertEqual(
            pseudonym_for_cluster(key, members),
            pseudonym_for_cluster(key, list(reversed(members))),
        )

    def test_duplicate_member_ids_do_not_change_pseudonym(self):
        key = b"k" * 32
        self.assertEqual(
            pseudonym_for_cluster(key, ["r1", "r2"]),
            pseudonym_for_cluster(key, ["r1", "r1", "r2"]),
        )

    def test_different_secret_changes_pseudonym(self):
        members = ["r1", "r2"]
        self.assertNotEqual(
            pseudonym_for_cluster(b"a" * 32, members),
            pseudonym_for_cluster(b"b" * 32, members),
        )

    def test_pseudonym_has_expected_prefix_and_alphabet(self):
        code = pseudonym_for_cluster(b"k" * 32, ["r1"])
        self.assertTrue(code.startswith("PSN-"))
        body = code[len("PSN-"):]
        self.assertTrue(all(c in "0123456789ABCDEFGHJKMNPQRSTVWXYZ" for c in body))

    def test_duplicate_file_path_does_not_change_existing_pseudonym(self):
        """Adding an exact duplicate FILE (same content, different path) to a cluster
        must not change the pseudonym already assigned to that cluster -- duplicate
        paths are distinct record ids, but content_anchor() collapses them.
        """
        same_sha = "f" * 64
        original = make_record_id(same_sha, "original/path.csv", "row:0")
        duplicate = make_record_id(same_sha, "backup/copy.csv", "row:0")
        key = b"k" * 32
        before = pseudonym_for_cluster(key, [original])
        after = pseudonym_for_cluster(key, [original, duplicate])
        self.assertEqual(before, after)


class BuildPseudonymMapTests(unittest.TestCase):
    def test_unresolved_records_get_no_pseudonym(self):
        assignments = [
            ClusterAssignment(record_id="a", cluster_key=None, decision="UNRESOLVED", evidence_codes=[]),
        ]
        result = build_pseudonym_map(b"k" * 32, assignments)
        self.assertIsNone(result["a"])

    def test_linked_records_share_pseudonym(self):
        assignments = [
            ClusterAssignment(record_id="a", cluster_key="a", decision="MUST_LINK", evidence_codes=[]),
            ClusterAssignment(record_id="b", cluster_key="a", decision="MUST_LINK", evidence_codes=[]),
        ]
        result = build_pseudonym_map(b"k" * 32, assignments)
        self.assertIsNotNone(result["a"])
        self.assertEqual(result["a"], result["b"])

    def test_different_clusters_get_different_pseudonyms(self):
        assignments = [
            ClusterAssignment(record_id="a", cluster_key="a", decision="MUST_LINK", evidence_codes=[]),
            ClusterAssignment(record_id="b", cluster_key="a", decision="MUST_LINK", evidence_codes=[]),
            ClusterAssignment(record_id="c", cluster_key="c", decision="MUST_LINK", evidence_codes=[]),
            ClusterAssignment(record_id="d", cluster_key="c", decision="MUST_LINK", evidence_codes=[]),
        ]
        result = build_pseudonym_map(b"k" * 32, assignments)
        self.assertNotEqual(result["a"], result["c"])


if __name__ == "__main__":
    unittest.main()
