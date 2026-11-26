"""O7: evidence ledger.

Keeps a per-record-pair audit trail of why a link was made or refused, so clustering can
check "is this merge supported by direct evidence, or only by a transitive A-B-C bridge of
weak evidence?" before committing to it. Contains no raw PII: only record ids and reason
codes, so it is safe to keep around and even log at debug level if ever needed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .scoring import PairVerdict


@dataclass
class EvidenceLedger:
    verdicts: dict[tuple[str, str], PairVerdict] = field(default_factory=dict)

    def record(self, verdict: PairVerdict) -> None:
        key = tuple(sorted((verdict.record_a, verdict.record_b)))
        self.verdicts[key] = verdict

    def verdict_for(self, a: str, b: str) -> PairVerdict | None:
        return self.verdicts.get(tuple(sorted((a, b))))

    def is_direct_strong_link(self, a: str, b: str) -> bool:
        v = self.verdict_for(a, b)
        if not v or not v.link:
            return False
        return "shared_strong_identifier" in v.reason_codes or "shared_name" in v.reason_codes

    def has_hard_conflict(self, a: str, b: str) -> bool:
        v = self.verdict_for(a, b)
        return bool(v and v.hard_conflict)
