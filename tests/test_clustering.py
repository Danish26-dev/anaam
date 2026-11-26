"""O6/O7 regression tests: the specific conflict scenarios clustering.py promises to
handle correctly in its docstring (hard conflicts, transitive bridges, homonyms,
duplicate files, no-evidence abstention).
"""
from __future__ import annotations

import unittest

import tests.conftest_path  # noqa: F401

from core.interfaces import IdentityEvidence
from identity.clustering import cluster_records


def _decisions(assignments) -> dict[str, tuple[str, str | None]]:
    return {a.record_id: (a.decision, a.cluster_key) for a in assignments}


class ClusteringTests(unittest.TestCase):
    def test_shared_strong_identifier_links_two_records(self):
        evidence = {
            "f1:row:0": IdentityEvidence(
                record_id="f1:row:0", patient_names=["Deepak Verma"],
                national_ids={"AADHAAR": "123498765432"},
            ),
            "f2:doc": IdentityEvidence(
                record_id="f2:doc", patient_names=["Deepak Verma"],
                national_ids={"AADHAAR": "123498765432"},
            ),
        }
        assignments, _ = cluster_records(evidence)
        decisions = _decisions(assignments)
        self.assertEqual(decisions["f1:row:0"][0], "MUST_LINK")
        self.assertEqual(decisions["f1:row:0"][1], decisions["f2:doc"][1])

    def test_homonyms_with_different_national_ids_never_merge(self):
        """Two different people sharing a name must stay apart even though the name
        alone would otherwise be a (weak) blocking key.
        """
        evidence = {
            "f3:row:0": IdentityEvidence(
                record_id="f3:row:0", patient_names=["Ramesh Kumar"],
                national_ids={"AADHAAR": "111111111111"}, age=40, gender="M",
            ),
            "f4:row:0": IdentityEvidence(
                record_id="f4:row:0", patient_names=["Ramesh Kumar"],
                national_ids={"AADHAAR": "222222222222"}, age=41, gender="M",
            ),
        }
        assignments, _ = cluster_records(evidence)
        decisions = _decisions(assignments)
        self.assertEqual(decisions["f3:row:0"][1], None)
        self.assertEqual(decisions["f4:row:0"][1], None)

    def test_transitive_bridge_through_hard_conflict_is_blocked(self):
        """A-B links on one weak clue, B-C links on a different weak clue, but A-C has a
        contradictory national ID. The merge must not go through even though neither
        single pair looked wrong on its own.
        """
        evidence = {
            "A": IdentityEvidence(
                record_id="A", patient_names=["Amit Shah"],
                national_ids={"AADHAAR": "111111111111"},
                date_of_birth="1980-01-01",
            ),
            "B": IdentityEvidence(
                record_id="B", patient_names=["Amit Shah"],
                date_of_birth="1980-01-01",
                relative_names=["Sunita Shah"],
            ),
            "C": IdentityEvidence(
                record_id="C", patient_names=["Amit Shah"],
                national_ids={"AADHAAR": "222222222222"},
                relative_names=["Sunita Shah"],
            ),
        }
        assignments, _ = cluster_records(evidence)
        decisions = _decisions(assignments)
        # A and C must never end up in the same cluster, directly or transitively.
        self.assertNotEqual(decisions["A"][1], decisions["C"][1])

    def test_cross_format_dob_match_links_despite_different_syntax(self):
        evidence = {
            "f5:row:0": IdentityEvidence(
                record_id="f5:row:0", patient_names=["Meena Joshi"],
                date_of_birth="1972-08-15",
            ),
            "f6:doc": IdentityEvidence(
                record_id="f6:doc", patient_names=["Meena Joshi"],
                date_of_birth="15/08/1972",
            ),
        }
        assignments, _ = cluster_records(evidence)
        decisions = _decisions(assignments)
        self.assertEqual(decisions["f5:row:0"][1], decisions["f6:doc"][1])
        self.assertIsNotNone(decisions["f5:row:0"][1])

    def test_record_with_no_evidence_stays_unresolved(self):
        evidence = {"lonely:doc": IdentityEvidence(record_id="lonely:doc")}
        assignments, _ = cluster_records(evidence)
        decisions = _decisions(assignments)
        self.assertEqual(decisions["lonely:doc"], ("UNRESOLVED", None))

    def test_shared_name_without_supporting_clue_does_not_link(self):
        """Same name alone (no DOB/relative/location match, no strong ID) must not link
        -- the published rule requires a supporting clue beyond the bare name.
        """
        evidence = {
            "x:row:0": IdentityEvidence(record_id="x:row:0", patient_names=["Sanjay Rathore"]),
            "y:row:0": IdentityEvidence(record_id="y:row:0", patient_names=["Sanjay Rathore"]),
        }
        assignments, _ = cluster_records(evidence)
        decisions = _decisions(assignments)
        self.assertIsNone(decisions["x:row:0"][1])
        self.assertIsNone(decisions["y:row:0"][1])


if __name__ == "__main__":
    unittest.main()
