"""Integration seam between Omkar's pipeline and Danish's detection engine.

The pipeline and writers import only this module. Call order in `main.py`:

    configure(keys.filename_key)        # once, before anything else here
    failures = prepare(file_envelopes)  # pass 1 over ALL files, then per-record detection
    extract_identity_evidence(record)   # evidence for identity resolution
    sanitize_path / sanitize_header / sanitize_keys   # hidden channels
    render_text(value, offset, record_id, field_path)  # writers (export/text_writer.py)

Span policy:
  * Spans computed for a record field are used only while the writer still holds the field's
    original value. A value the pipeline rewrote (generalised village, duplicate header) is
    scanned on its own instead; issued pseudonyms are exempt from that scan.
  * Whole-field age, village and PIN spans are dropped when the pipeline recognises the
    column's role (core.header_roles), because the privacy layer generalises it truthfully
    and that earns utility. Columns it does not recognise stay with the engine. Dates and
    DOBs (SHIFT_DATE) are passed to the writer, which shifts them by the record's offset.
  * Text with no record context (file-level metadata, keys, narratives the pipeline
    rewrote) is scanned with the engine's harvested lexicon, so known names and IDs are
    still caught.

Nothing here prints, logs or stores values outside process memory.
"""
from __future__ import annotations

import dataclasses
import re

from core import interfaces as c
from core.header_roles import role_for_header
from core.interfaces import IdentityEvidence, RecordEnvelope, ResolvedSpan

from .engine import DetectionEngine, apply_placeholders

# Whole-field actions the privacy layer owns, keyed to the header role it recognises
# (core.header_roles). A column it does not recognise stays with the engine.
_PRIVACY_LAYER_AGE_ROLES = frozenset({"age", "age_sex"})
_PRIVACY_LAYER_ROLE = {c.GENERALIZE_LOCATION: "village", c.GENERALIZE_PIN: "pin"}
_KEPT_ACTIONS = frozenset({c.KEEP, c.SHIFT_DATE, c.GENERALIZE_AGE})
# Pseudonym format issued by privacy/pseudonyms.py ("PSN-" + Crockford base32).
_PSEUDONYM = re.compile(r"(?:Patient/)?PSN-[0-9A-HJKMNP-TV-Z]{4,}")

_engine: DetectionEngine | None = None
_context: dict[tuple[str, str], tuple[str, list[ResolvedSpan]]] = {}
_evidence: dict[str, IdentityEvidence] = {}
_order: dict[str, str] = {}


def configure(filename_key: bytes) -> None:
    """Start a fresh engine for one run. `filename_key` is derived from RAKSHA_SECRET."""
    global _engine
    _engine = DetectionEngine(filename_key=filename_key)
    _context.clear()
    _evidence.clear()
    _order.clear()


def engine() -> DetectionEngine:
    """The run's engine; a keyless default exists only for unit tests that skip configure()."""
    global _engine
    if _engine is None:
        _engine = DetectionEngine()
    return _engine


def _engine_view(f: c.FileEnvelope) -> c.FileEnvelope:
    """The adapters' envelope in the engine's conventions: content fields only, with
    role_hint set to the CSV header (paths are "col:<Header>") or the JSON key."""
    records = []
    for r in f.records:
        fields = []
        for n in r.fields:
            if n.channel not in (c.CONTENT, c.METADATA, c.BASE64, c.FHIR_NARRATIVE):
                continue  # header cells and keys are handled by sanitize_header / sanitize_keys
            hint = n.role_hint
            if not hint:
                if n.path.startswith("col:"):
                    hint = n.path[4:]
                elif n.path.startswith("/"):
                    hint = n.path.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
            fields.append(dataclasses.replace(n, role_hint=hint))
        records.append(dataclasses.replace(r, fields=fields))
    return dataclasses.replace(f, records=records)


def prepare(files: list[c.FileEnvelope]) -> dict[str, str]:
    """Harvest identities across every file, then detect every record.

    Returns {input_sha256: reason_code} for files whose detection failed; the caller
    quarantines them. Never raises for a single bad file."""
    eng = engine()
    views = [_engine_view(f) for f in files]
    eng.prepare(views)
    failures: dict[str, str] = {}
    for view in views:
        try:
            for r in view.records:
                det = eng.detect_record(r, view)
                values = {n.path: str(n.value) for n in r.fields if n.value is not None}
                if r.free_text:
                    values[""] = r.free_text
                hints = {n.path: n.role_hint or "" for n in r.fields}
                by_path: dict[str, list[ResolvedSpan]] = {}
                for s in det.spans:
                    by_path.setdefault(s.field_path, []).append(s)
                for path, value in values.items():
                    _context[(r.record_id, path)] = (value, by_path.get(path, []), hints.get(path, ""))
                if det.evidence is not None:
                    _evidence[r.record_id] = det.evidence
            _order[view.input_sha256] = eng._date_order.get(view.input_sha256, "dmy")
        except (RecursionError, ValueError, KeyError, IndexError, TypeError):
            failures[view.input_sha256] = "detection_failed"
    return failures


def field_spans(record_id: str | None, field_path: str | None, value: str) -> list[ResolvedSpan] | None:
    """Spans for a record field, or None if there is no usable context for it.

    None means "scan the value on its own": no context, or the writer holds a different
    value from the one detection saw (rewritten by the pipeline, or a duplicate header)."""
    if record_id is None or field_path is None:
        return None
    entry = _context.get((record_id, field_path))
    if entry is None:
        return None
    original, spans, hint = entry
    if value != original:
        return None
    pipeline_role = role_for_header(hint) if hint else None
    out = []
    for s in spans:
        if s.reason_code != "field":
            out.append(s)
            continue
        if s.action == c.GENERALIZE_AGE and pipeline_role in _PRIVACY_LAYER_AGE_ROLES:
            continue  # the privacy layer generalises this column truthfully (plain age
            # or a combined "age/gender" cell -- apply_generalization.py handles both)
        if s.action in _PRIVACY_LAYER_ROLE and _PRIVACY_LAYER_ROLE[s.action] == pipeline_role:
            continue  # the privacy layer generalises this column truthfully
        out.append(s)
    return out


def resolve_spans(text: str) -> list[ResolvedSpan]:
    """Context-free detection with the harvested lexicon. Issued pseudonyms are not PII."""
    if _PSEUDONYM.fullmatch(text.strip()):
        return []
    return engine().detect_text(text)


def apply_spans(text: str, spans: list[ResolvedSpan]) -> tuple[str, int]:
    """Apply spans with typed placeholders. Returns (new_text, edits)."""
    if not spans:
        return text, 0
    edits = sum(1 for s in spans if not (s.action in _KEPT_ACTIONS and s.category != c.DOB))
    return apply_placeholders(text, spans), edits


def number_is_identifier(record_id: str | None, field_path: str | None, value: int | float) -> bool:
    """True if a JSON number holds PII (an Aadhaar or phone stored as a number). The caller
    replaces it with 0 so the JSON type is preserved."""
    text = str(value)
    spans = field_spans(record_id, field_path, text)
    if spans is None:
        spans = resolve_spans(text)
    return any(not (s.action in _KEPT_ACTIONS and s.category != c.DOB) for s in spans)


def extract_identity_evidence(
    record: RecordEnvelope,
    fallback_text: str | None = None,
) -> IdentityEvidence:
    """Evidence produced by prepare(); empty evidence if the record was not prepared."""
    return _evidence.get(record.record_id) or IdentityEvidence(record_id=record.record_id)


def sanitize_path(rel_path: str) -> str:
    return engine().sanitize_path(rel_path)


def sanitize_header(cells: list[str]) -> list[str]:
    return engine().sanitize_header(cells)


def sanitize_keys(keys: list[str]) -> dict[str, str]:
    return engine().sanitize_keys(keys)


def date_order(input_sha256: str) -> str | None:
    return _order.get(input_sha256)
