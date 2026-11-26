"""O7: deterministic constrained clustering with direct conflict checks."""
from __future__ import annotations

from dataclasses import dataclass

from core.interfaces import ClusterAssignment, IdentityEvidence
from .blocking import CandidatePair, generate_candidates
from .evidence_ledger import EvidenceLedger
from .scoring import PairVerdict, has_hard_conflict, score_pair


@dataclass
class _UnionFind:
    parent: dict[str, str]
    members: dict[str, set[str]]

    @classmethod
    def create(cls, record_ids: set[str]) -> "_UnionFind":
        return cls(
            parent={record_id: record_id for record_id in record_ids},
            members={record_id: {record_id} for record_id in record_ids},
        )

    def find(self, value: str) -> str:
        root = value
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[value] != value:
            parent = self.parent[value]
            self.parent[value] = root
            value = parent
        return root

    def group(self, value: str) -> set[str]:
        return self.members[self.find(value)]

    def union(self, left: str, right: str) -> str:
        root_left, root_right = self.find(left), self.find(right)
        if root_left == root_right:
            return root_left
        if root_right < root_left:
            root_left, root_right = root_right, root_left
        self.parent[root_right] = root_left
        self.members[root_left].update(self.members.pop(root_right))
        return root_left


def cluster_records(
    evidence_by_record: dict[str, IdentityEvidence],
) -> tuple[list[ClusterAssignment], EvidenceLedger]:
    ledger = EvidenceLedger()
    all_ids = set(evidence_by_record)
    union_find = _UnionFind.create(all_ids)

    verdicts: list[PairVerdict] = []
    for pair in generate_candidates(evidence_by_record):
        verdict = score_pair(
            pair,
            evidence_by_record[pair.record_a],
            evidence_by_record[pair.record_b],
        )
        ledger.record(verdict)
        verdicts.append(verdict)

    # MUST edges are considered first. PROBABLE edges may join only two singleton
    # clusters, so weak evidence can never propagate through an A-B-C bridge.
    strength_rank = {"MUST": 0, "PROBABLE": 1}
    linking = sorted(
        (verdict for verdict in verdicts if verdict.link),
        key=lambda verdict: (
            strength_rank.get(verdict.strength, 2), verdict.record_a, verdict.record_b
        ),
    )
    accepted_edges: list[PairVerdict] = []

    for verdict in linking:
        root_a, root_b = union_find.find(verdict.record_a), union_find.find(verdict.record_b)
        if root_a == root_b:
            continue
        members_a, members_b = union_find.group(root_a), union_find.group(root_b)

        # Compare raw evidence for every cross-cluster pair. This catches conflicts even
        # when that pair never shared a blocking key and therefore has no ledger verdict.
        conflict = any(
            has_hard_conflict(evidence_by_record[a], evidence_by_record[b])
            for a in members_a
            for b in members_b
        )
        if conflict:
            continue

        if verdict.strength == "PROBABLE" and (len(members_a) != 1 or len(members_b) != 1):
            continue

        union_find.union(verdict.record_a, verdict.record_b)
        accepted_edges.append(verdict)

    groups = [sorted(members) for members in union_find.members.values()]
    groups.sort(key=lambda members: members[0])
    assignments: list[ClusterAssignment] = []

    for members in groups:
        if len(members) == 1:
            assignments.append(
                ClusterAssignment(
                    record_id=members[0],
                    cluster_key=None,
                    decision="UNRESOLVED",
                    evidence_codes=["no_accepted_link"],
                )
            )
            continue

        member_set = set(members)
        group_edges = [
            edge
            for edge in accepted_edges
            if edge.record_a in member_set and edge.record_b in member_set
        ]
        decision = "MUST_LINK" if any(edge.strength == "MUST" for edge in group_edges) else "PROBABLE_LINK"
        cluster_key = min(members)

        for record_id in members:
            codes = sorted(
                {
                    code
                    for edge in group_edges
                    if record_id in (edge.record_a, edge.record_b)
                    for code in edge.reason_codes
                }
            )
            assignments.append(
                ClusterAssignment(
                    record_id=record_id,
                    cluster_key=cluster_key,
                    decision=decision,
                    evidence_codes=codes or ["accepted_transitive_member"],
                )
            )

    assignments.sort(key=lambda assignment: assignment.record_id)
    return assignments, ledger
