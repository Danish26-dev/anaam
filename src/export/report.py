"""O12: report.json builder.

Every count here must be cross-checkable against what was actually written to disk --
never claim more than was delivered (false-success is explicitly, heavily penalised).
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ReportCounts:
    files_total: int = 0
    files_sanitized: int = 0
    files_quarantined: int = 0
    records_processed: int = 0
    identifiers_detected: int = 0
    records_linked: int = 0
    records_generalized: int = 0
    records_suppressed: int = 0
    records_quarantined: int = 0


@dataclass
class FileReportEntry:
    input_sha256: str
    output: str | None
    status: str  # "sanitized" | "quarantined" | "suppressed"
    reason: str | None = None


@dataclass
class ReportBuilder:
    files: list[FileReportEntry] = field(default_factory=list)
    entities: dict[str, int] = field(default_factory=dict)
    seconds: float = 0.0
    peak_rss_mb: float = 0.0

    def add_file(self, entry: FileReportEntry) -> None:
        self.files.append(entry)

    def add_entity_counts(self, counts: dict[str, int]) -> None:
        for k, v in counts.items():
            self.entities[k] = self.entities.get(k, 0) + v

    def counts(self, records_processed: int, records_linked: int, records_generalized: int,
               records_suppressed: int, identifiers_detected: int,
               records_quarantined: int = 0) -> ReportCounts:
        n_san = sum(1 for f in self.files if f.status == "sanitized")
        n_quar = sum(1 for f in self.files if f.status == "quarantined")
        return ReportCounts(
            files_total=len(self.files),
            files_sanitized=n_san,
            files_quarantined=n_quar,
            records_processed=records_processed,
            identifiers_detected=identifiers_detected,
            records_linked=records_linked,
            records_generalized=records_generalized,
            records_suppressed=records_suppressed,
            records_quarantined=records_quarantined,
        )

    def build(self, counts: ReportCounts) -> dict:
        report = {
            "schema": "raksha-report/1",
            "files": [
                {k: v for k, v in {
                    "input_sha256": f.input_sha256,
                    "output": f.output,
                    "status": f.status,
                    "reason": f.reason,
                }.items() if v is not None or k != "reason"}
                for f in self.files
            ],
            "counts": vars(counts),
            "timing": {"seconds": round(self.seconds, 2)},
            "resources": {"peak_rss_mb": self.peak_rss_mb},
        }
        # Typed entity counts become available when Danish's resolved-span detector is
        # integrated. Omit the optional field until then instead of publishing an empty
        # breakdown beside a non-zero aggregate.
        if self.entities:
            report["entities"] = dict(sorted(self.entities.items()))
        return report

    def write(self, output_dir: Path, counts: ReportCounts) -> None:
        report = self.build(counts)
        content = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        destination = output_dir / "report.json"
        temporary = output_dir / ".report.json.tmp"
        try:
            temporary.write_text(content, encoding="utf-8", newline="")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)


def peak_rss_mb() -> float:
    try:
        import resource

        r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(r / 1024 if sys.platform != "darwin" else r / 1048576, 1)
    except Exception:  # noqa: BLE001 - resource module is POSIX-only (not on Windows)
        return 0.0
