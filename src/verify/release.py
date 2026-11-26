"""D9: release gate. Decides RELEASE / RESCRUB / QUARANTINE per file, ABORT only for
release-level breakage. Fail closed, never print or return matched values.

File failure    -> rescrub once, verify again, else quarantine and continue.
Release failure -> abort safely: unaccounted input, report/manifest inconsistent with the
                   exported tree, or the secret appearing anywhere in the output.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from .. import contracts as c
from ..detection.engine import DetectionEngine, apply_placeholders
from .clinical import clinical_loss
from .leaks import LeakVerifier
from . import structure as st

SAFE_CODES = {"KNOWN_NAME", "KNOWN_ID", "KNOWN_PLACE", "NOT_UTF8", "CSV_UNPARSEABLE", "CSV_ROW_COUNT",
              "CSV_HEADER_WIDTH", "JSON_UNPARSEABLE", "JSON_PATHS_LOST", "JSON_TYPE_CHANGED",
              "FHIR_NOT_BUNDLE", "FHIR_UNRESOLVED_REFERENCE", "PSEUDONYM_MISSING"}


def _code(finding: c.LeakFinding) -> str:
    return finding.category   # already a safe label: KNOWN_*, RESIDUAL_<CATEGORY>


@dataclass
class FileCandidate:
    """What the pipeline hands to the verifier for one output file."""
    text: str                           # candidate output as text (UTF-8)
    original_text: str | None = None    # input text, for the clinical comparison
    fmt: str = "text"                   # text | csv | tsv | json | fhir
    pseudonyms: tuple[str, ...] = ()    # pseudonyms that must appear (one per claimed record)
    n_columns: int | None = None
    n_rows: int | None = None
    delimiter: str = ","
    original_json: object | None = None
    exempt_json_prefixes: tuple[str, ...] = ()
    order: str | None = None


class ReleaseGate:
    def __init__(self, engine: DetectionEngine, allowed_tokens: set[str] | None = None,
                 max_clinical_loss: float = 0.0, secret: str | None = None) -> None:
        self.engine = engine
        self.leaks = LeakVerifier(engine, allowed_tokens)
        self.max_clinical_loss = max_clinical_loss
        self._secret = secret

    def prepare(self) -> None:
        self.leaks.refresh()

    # ------------------------------------------------------------------ one file
    def verify_file(self, cand: FileCandidate) -> c.VerificationResult:
        codes: list[str] = []
        header_len = (cand.text.find("\n") + 1 or len(cand.text)) if cand.fmt in ("csv", "tsv") else 0
        findings = self.leaks.scan(cand.text, cand.order, structured=cand.fmt in ("csv", "tsv", "json", "fhir"),
                                   header_len=header_len)
        codes += sorted({_code(f) for f in findings})
        codes += self._structure(cand)
        if cand.original_text is not None:
            lost = clinical_loss(cand.original_text, cand.text)
            n_before = max(1, sum(1 for _ in self._count(cand.original_text)))
            if sum(lost.values()) / n_before > self.max_clinical_loss:
                codes += [f"CLINICAL_LOSS_{k}" for k in sorted(lost)]
        if self._secret and self._secret in cand.text:
            return c.VerificationResult(False, ["SECRET_IN_OUTPUT"], False, c.ABORT_RELEASE, findings)
        if not codes:
            return c.VerificationResult(True, [], False, c.RELEASE, [])
        structural = [x for x in codes if x in SAFE_CODES and not x.startswith(("KNOWN_", "RESIDUAL_"))]
        retry = bool(findings) and not structural
        return c.VerificationResult(False, codes, retry, c.RESCRUB if retry else c.QUARANTINE, findings)

    def _count(self, text):
        from ..detection.clinical import detect_clinical
        return [s for s in detect_clinical(text) if s.proposed_action == c.KEEP]

    def _structure(self, cand: FileCandidate) -> list[str]:
        codes = st.check_utf8(cand.text.encode("utf-8", errors="surrogatepass"))
        if cand.fmt in ("csv", "tsv") and cand.n_columns is not None and cand.n_rows is not None:
            codes += st.check_csv(cand.text, cand.delimiter, cand.n_columns, cand.n_rows)
        elif cand.fmt in ("json", "fhir"):
            errs, parsed = st.check_json(cand.text)
            codes += errs
            if parsed is not None:
                if cand.original_json is not None:
                    codes += st.check_json_shape(cand.original_json, parsed, cand.exempt_json_prefixes)
                if cand.fmt == "fhir":
                    codes += st.check_fhir_references(parsed)
        for p in cand.pseudonyms:
            codes += st.check_pseudonym_present(cand.text, p)
        return sorted(set(codes))

    # ------------------------------------------------------------------ rescrub loop
    def rescrub_text(self, text: str, order: str | None = None) -> str:
        spans = [s for s in self.engine.detect_text(text, order)
                 if s.action != c.KEEP and s.category not in self.leaks.allowed_categories]
        extra = self._known_spans(text)
        return apply_placeholders(text, spans + extra)

    def _known_spans(self, text: str) -> list[c.ResolvedSpan]:
        out = []
        for f in self.leaks.scan_known(text):
            if f.start >= 0:
                cat = c.PERSON_NAME if f.category == "KNOWN_NAME" else (
                    c.MRN if f.category == "KNOWN_ID" else c.VILLAGE)
                out.append(c.ResolvedSpan(f.start, f.end, cat, c.REDACT, "verifier"))
        return out

    def verify_and_fix(self, cand: FileCandidate, rescrub: Callable[[FileCandidate], FileCandidate] | None = None
                       ) -> tuple[c.VerificationResult, FileCandidate]:
        """Verify; on a leak rescrub once (text formats only) and verify again; else quarantine."""
        res = self.verify_file(cand)
        if res.terminal_action != c.RESCRUB:
            return res, cand
        fixed = rescrub(cand) if rescrub else FileCandidate(**{**cand.__dict__, "text": self.rescrub_text(cand.text, cand.order)})
        res2 = self.verify_file(fixed)
        if res2.passed:
            res2.safe_reason_codes = ["RESCRUBBED"]
            return res2, fixed
        res2.terminal_action = c.QUARANTINE
        res2.retry_allowed = False
        return res2, fixed

    # ------------------------------------------------------------------ release level
    def verify_release(self, report: dict, records: list[dict], exported: set[str], input_shas: set[str]) -> c.VerificationResult:
        codes = []
        listed = {e.get("input_sha256") for e in report.get("files", [])}
        if not input_shas <= listed:
            codes.append("UNACCOUNTED_INPUT")
        for e in report.get("files", []):
            if e.get("status") == "sanitized" and (not e.get("output") or
                                                   str(e["output"]).replace("sanitized/", "", 1) not in exported):
                codes.append("REPORT_OUTPUT_MISSING")
                break
        cnt = report.get("counts", {})
        sanitized = sum(1 for e in report.get("files", []) if e.get("status") == "sanitized")
        quarantined = sum(1 for e in report.get("files", []) if e.get("status") == "quarantined")
        if cnt.get("files_total") != len(report.get("files", [])) or cnt.get("files_sanitized") != sanitized \
                or cnt.get("files_quarantined") != quarantined:
            codes.append("REPORT_COUNTS_INCONSISTENT")
        for r in records:
            if str(r.get("file", "")).replace("sanitized/", "", 1) not in exported:
                codes.append("RECORD_FILE_MISSING")
                break
        for name, blob in (("REPORT", json.dumps(report, ensure_ascii=False)),
                           ("RECORDS", "\n".join(json.dumps(r, ensure_ascii=False) for r in records))):
            if self._secret and self._secret in blob:
                codes.append("SECRET_IN_OUTPUT")
            if self.leaks.scan_known(blob):
                codes.append(f"{name}_LEAK")
        if codes:
            return c.VerificationResult(False, sorted(set(codes)), False, c.ABORT_RELEASE)
        return c.VerificationResult(True, [], False, c.RELEASE)
