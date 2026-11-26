"""Detection engine: the single entry point Omkar's pipeline calls.

    engine = DetectionEngine(filename_key=keys.filename)
    engine.prepare(files)                      # pass 1: classify fields, harvest identities
    det = engine.detect_record(record, file)   # pass 2: ResolvedSpans + IdentityEvidence
    new_path = engine.sanitize_path(rel_path)  # hidden channel: file and folder names
    cells = engine.sanitize_header(cells)      # hidden channel: CSV header cells
    keys = engine.sanitize_keys(keys)          # hidden channel: JSON object keys

Conventions expected from the adapters (see docs/DANISH_NOTES.md):
  * CSV/TSV row fields: path "col:<j>", role_hint = header text.
  * JSON fields: path = RFC 6901 pointer from the file root, role_hint = last key.
  * FHIR: format "fhir", same JSON pointer convention.
  * Text: RecordEnvelope.free_text (field_path "").
All spans are in ORIGINAL string offsets of the field value.
Nothing in this module prints, logs or persists values.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass, field

try:
    from .. import contracts as c
except ImportError:  # loaded as a top-level `detection` package (Omkar's sys.path layout)
    import contracts as c
from . import field_classifier as fc
from .address import address_segments, detect_address_components
from .attachments import find_payloads, sanitize_payload
from .clinical import detect_clinical, doctor_name_spans
from .dates import detect_dates_and_ages, find_dates, infer_order
from .identifiers import detect_identifiers, id_digit_core, id_scope
from .identity_lexicon import ROLE_DOCTOR, ROLE_OTHER, ROLE_PATIENT, ROLE_RELATIVE, IdentityLexicon
from .names import detect_names, trim_name
from .normalization import TextView, digits_only
from .span_resolver import resolve

PLACEHOLDER = {
    c.PATIENT_NAME: "[PATIENT]", c.RELATIVE_NAME: "[RELATIVE]", c.PERSON_NAME: "[PERSON]",
    c.PHONE: "[PHONE]", c.PHONE_MASKED: "[PHONE]", c.EMAIL: "[EMAIL]", c.AADHAAR: "[AADHAAR]",
    c.AADHAAR_MASKED: "[AADHAAR]", c.ABHA_NUMBER: "[ABHA]", c.ABHA_ADDRESS: "[ABHA]", c.PAN: "[PAN]",
    c.MRN: "[ID]", c.INSURANCE_ID: "[INSURANCE-ID]", c.OTHER_ID: "[ID]", c.DOB: "[DOB]",
    c.ADDRESS: "[ADDRESS]", c.HOUSE: "[HOUSE]", c.LOCALITY: "[LOCALITY]", c.LANDMARK: "[LANDMARK]",
    c.VILLAGE: "[VILLAGE]", c.PIN: "[PIN]", c.PAYLOAD: "[ATTACHMENT]",
}
# low-confidence name guesses: never enough on their own to rename a header, key or file
WEAK_SOURCES = frozenset({"postposition", "postposition_deva", "bigram", "lexicon_token"})
_RELATION_PREFIX = re.compile(
    r"^\s*(?:[SDWCH][ ]?/[ ]?[Oo]|[SDW]\.[ ]?[Oo]\.|son of|daughter of|wife of|husband of|care of|"
    r"पुत्र|पुत्री|पत्नी)\.?\s*[:\-]?\s*", re.IGNORECASE)
_EMPTY = re.compile(r"^\s*(?:|-+|n/?a|nil|none|null|unknown|not available|\.)\s*$", re.IGNORECASE)
_GENDER = {"m": "M", "male": "M", "man": "M", "पुरुष": "M", "f": "F", "female": "F", "woman": "F",
           "महिला": "F", "स्त्री": "F", "o": "O", "other": "O", "t": "O", "transgender": "O"}
_GENDER_IN_AGE = re.compile(r"\d\s*(?:Y|Yrs?|years?)?\s*/\s*(M|F|Male|Female)\b|(पुरुष|महिला)", re.IGNORECASE)
_PATH_NAME = re.compile(r"(?<![A-Za-z])([A-Z][a-z]{2,})_([A-Z][a-z]{2,})(?=[_\\/.\-]|\d|$)")
_FILE_NAME_PAIR = re.compile(r"(?<![A-Za-z])([A-Z][a-z]{2,})[_ ]([A-Z][a-z]{2,})(?![a-z])")


@dataclass
class RecordDetection:
    spans: list[c.ResolvedSpan] = field(default_factory=list)
    evidence: c.IdentityEvidence | None = None


def _pointer_parts(path: str) -> list[str]:
    if not path.startswith("/"):
        return [path]
    return [p.replace("~1", "/").replace("~0", "~") for p in path.split("/")[1:]]


def _pattern(path: str) -> str:
    return re.sub(r"/\d+(?=/|$)", "/*", path) if path.startswith("/") else path


def _span(s, e, category, action, source, field_path, attrs=None, replacement=None):
    return c.ResolvedSpan(s, e, category, action, source, field_path, replacement, attrs or {})


class DetectionEngine:
    def __init__(self, filename_key: bytes = b"dev-only-filename-key") -> None:
        self.lexicon = IdentityLexicon()
        self._field_class: dict[tuple[str, str], str] = {}
        self._date_order: dict[str, str] = {}
        self._fhir_types: dict[str, dict[str, str]] = {}
        self._filename_key = filename_key

    # ================================================================== pass 1
    def prepare(self, files: list[c.FileEnvelope]) -> None:
        for f in files:
            self._index_file(f)
        for f in files:
            self._harvest_structured(f)
        for f in files:
            self._harvest_context(f)

    def _index_file(self, f: c.FileEnvelope) -> None:
        texts, by_pattern, headers = [], {}, {}
        types: dict[str, str] = {}
        for r in f.records:
            if r.free_text:
                texts.append(r.free_text)
            for n in r.fields:
                if isinstance(n.value, str):
                    texts.append(n.value)
                if n.channel != c.CONTENT:
                    continue
                pat = _pattern(n.path)
                by_pattern.setdefault(pat, []).append(n.value)
                headers.setdefault(pat, n.role_hint or "")
                if n.path.endswith("/resourceType") and isinstance(n.value, str):
                    types[n.path[: -len("/resourceType")]] = n.value
        self._date_order[f.input_sha256] = infer_order(texts[:5000]) or "dmy"
        self._fhir_types[f.input_sha256] = types
        for pat, values in by_pattern.items():
            parts = _pointer_parts(pat)
            parents = tuple(p for p in parts[:-1] if p != "*")
            header = headers[pat] or (parts[-1] if parts else "")
            ftype = self._fhir_type(f, pat) if f.detected_format == "fhir" else None
            self._field_class[(f.input_sha256, pat)] = fc.classify_field(header, values[:500], parents, ftype)

    def _fhir_type(self, f: c.FileEnvelope, path: str) -> str:
        types = self._fhir_types.get(f.input_sha256, {})
        m = re.match(r"^(/entry/(?:\d+|\*)/resource)", path)
        if not m:
            return "Bundle"
        prefix = m.group(1)
        if prefix in types:
            return types[prefix]
        if "*" in prefix:  # pattern lookup: all entries share the same structure rarely; use any
            vals = {v for k, v in types.items()}
            return next(iter(vals)) if len(vals) == 1 else "Unknown"
        return "Unknown"

    def field_class(self, f: c.FileEnvelope, n: c.FieldNode) -> str:
        if f.detected_format == "fhir":
            parts = _pointer_parts(n.path)
            parents = tuple(p for p in parts[:-1] if not p.isdigit())
            return fc.classify_field(parts[-1] if parts else "", [n.value], parents, self._fhir_type(f, n.path))
        return self._field_class.get((f.input_sha256, _pattern(n.path)), fc.UNKNOWN)

    def _harvest_structured(self, f: c.FileEnvelope) -> None:
        for r in f.records:
            for n in r.fields:
                if n.channel != c.CONTENT or n.value is None:
                    continue
                v = str(n.value).strip()
                if not v or _EMPTY.match(v):
                    continue
                cls = self.field_class(f, n)
                if cls == fc.NAME_PATIENT:
                    self.lexicon.add_name(v, ROLE_PATIENT)
                elif cls == fc.NAME_RELATIVE:
                    self.lexicon.add_name(_RELATION_PREFIX.sub("", v), ROLE_RELATIVE)
                elif cls == fc.NAME_PERSON:
                    self.lexicon.add_name(v, ROLE_OTHER)
                elif cls == fc.NAME_DOCTOR:
                    self.lexicon.add_name(re.sub(r"^\s*(?:Dr|Doctor)\.?\s*", "", v, flags=re.I), ROLE_DOCTOR)
                elif cls in (fc.MRN, fc.OTHER_ID):
                    self.lexicon.add_id(v, c.MRN)
                elif cls == fc.PHONE:
                    self.lexicon.add_id(v, c.PHONE)
                elif cls == fc.AADHAAR:
                    self.lexicon.add_id(v, c.AADHAAR)
                elif cls == fc.ABHA_NUMBER:
                    self.lexicon.add_id(v, c.ABHA_NUMBER)
                elif cls == fc.INSURANCE_ID:
                    self.lexicon.add_id(v, c.INSURANCE_ID)
                elif cls == fc.VILLAGE:
                    self.lexicon.add_place(v, c.VILLAGE)

    def _harvest_context(self, f: c.FileEnvelope) -> None:
        for r in f.records:
            texts = [r.free_text] if r.free_text else []
            for n in r.fields:
                if isinstance(n.value, str) and n.channel == c.CONTENT and \
                        self.field_class(f, n) in (fc.FREE_TEXT, fc.UNKNOWN, fc.CLINICAL, fc.ADDRESS):
                    texts.append(n.value)
            for t in texts:
                view = TextView.of(t)
                for s, e in doctor_name_spans(view.text):
                    self.lexicon.add_name(view.text[s:e], ROLE_DOCTOR)
                for cand in detect_names(view.text):
                    if cand.tier != c.TIER_EXPLICIT_IDENTITY or cand.source in ("by", "bigram"):
                        continue
                    role = {c.PATIENT_NAME: ROLE_PATIENT, c.RELATIVE_NAME: ROLE_RELATIVE}.get(cand.category, ROLE_OTHER)
                    self.lexicon.add_name(view.text[cand.start:cand.end], role)
                for cand in detect_identifiers(view.text):
                    if cand.source == "id_label":
                        self.lexicon.add_id(view.text[cand.start:cand.end], c.MRN)

    # ================================================================== pass 2: text
    def detect_text(self, text: str, order: str | None = None, field_path: str = "",
                    ids_case_insensitive: bool = False, extra: list[c.SpanCandidate] | None = None,
                    depth: int = 0, id_shapes: bool = True) -> list[c.ResolvedSpan]:
        if not text or not text.strip():
            return []
        view = TextView.of(text)
        t = view.text
        cands: list[c.SpanCandidate] = []
        cands += detect_clinical(t)
        ident = detect_identifiers(t, self.lexicon.templates, ids_case_insensitive)
        if not id_shapes:  # a column of bill / sample / visit numbers: only known patient IDs
            ident = [x for x in ident if x.source != "id_shape"]
        cands += ident
        cands += detect_dates_and_ages(t, order)
        cands += detect_address_components(t)
        cands += detect_names(t)
        cands += self.lexicon.find(t)
        if "\\" in t or "/" in t or "_" in t:
            for m in _PATH_NAME.finditer(t):
                tr = trim_name(t, m.start(), m.end())
                if tr and all(trim_name(t, m.start(g), m.end(g)) for g in (1, 2)):
                    cands.append(c.SpanCandidate(m.start(), m.end(), c.PERSON_NAME, None, 0.7,
                                                 c.TIER_EXPLICIT_IDENTITY, "path_name", c.REDACT))
        if extra:
            cands += extra
        accepted = resolve(t, cands)
        out: list[c.ResolvedSpan] = []
        for s in accepted:
            a, b = view.span_to_original(s.start, s.end)
            out.append(_span(a, b, s.category, s.proposed_action, s.source, field_path,
                             self._attrs(text[a:b], s, order)))
        if depth < 2:
            out = self._with_payloads(text, out, order, field_path, depth)
        return out

    def _with_payloads(self, text, spans, order, field_path, depth):
        payloads = find_payloads(text)
        if not payloads:
            return spans
        out = list(spans)
        for p in payloads:
            repl, changed = sanitize_payload(
                p, lambda inner: self._scrub_count(inner, order, depth + 1))
            if not changed:
                continue
            out = [s for s in out if s.end <= p.start or s.start >= p.end]
            out.append(_span(p.start, p.end, c.PAYLOAD, c.REENCODE, f"payload:{p.encoding}", field_path,
                             {"binary": p.binary}, repl))
        out.sort(key=lambda s: (s.start, s.end))
        return out

    def _attrs(self, surface: str, s: c.SpanCandidate, order: str | None) -> dict:
        if s.category in (c.DATE, c.DOB):
            found = find_dates(surface, order)
            if found and found[0][2] is not None:
                return {"date": found[0][2].isoformat(), "format": found[0][3]}
            return {"format": found[0][3] if found else "unknown"}
        if s.category == c.AGE:
            d = digits_only(surface)
            return {"age": int(d)} if d else {}
        return {}

    def scrub_text(self, text: str, order: str | None = None) -> str:
        """Text with every edit replaced by a typed placeholder (dates/ages kept)."""
        return self._scrub_count(text, order, 0)[0]

    def _scrub_count(self, text: str, order: str | None, depth: int) -> tuple[str, int]:
        spans = self.detect_text(text, order, depth=depth)
        return apply_placeholders(text, spans), sum(1 for s in spans if s.action not in (c.KEEP,))

    # ================================================================== pass 2: records
    def detect_record(self, record: c.RecordEnvelope, f: c.FileEnvelope) -> RecordDetection:
        order = self._date_order.get(f.input_sha256, "dmy")
        spans: list[c.ResolvedSpan] = []
        classes: dict[str, str] = {}
        for n in record.fields:
            if n.value is None or isinstance(n.value, bool):
                continue
            value = str(n.value)
            if n.channel in (c.HEADER, c.KEY, c.FILENAME):
                spans += self.detect_text(value, order, n.path, ids_case_insensitive=True)
                continue
            cls = self.field_class(f, n)
            classes[n.path] = cls
            spans += self._field_spans(value, cls, order, n.path)
        if record.free_text:
            spans += self.detect_text(record.free_text, order, "")
        return RecordDetection(spans, self._evidence(record, spans, classes, f))

    def _field_spans(self, value: str, cls: str, order: str, path: str) -> list[c.ResolvedSpan]:
        stripped = value.strip()
        if not stripped or _EMPTY.match(value):
            return []
        s0 = value.index(stripped[0])
        e0 = s0 + len(stripped)
        whole = None
        if cls == fc.NAME_PATIENT:
            whole = (c.PATIENT_NAME, c.PSEUDONYMIZE)
        elif cls == fc.NAME_PERSON:
            whole = (c.PERSON_NAME, c.REDACT)
        elif cls == fc.NAME_RELATIVE:
            m = _RELATION_PREFIX.match(value)
            if m and m.end() < e0:
                s0 = m.end()
            return [_span(s0, e0, c.RELATIVE_NAME, c.REDACT, "field", path)]
        elif cls in fc.DIRECT_ID_CLASSES:
            cat = {fc.PHONE: c.PHONE, fc.EMAIL: c.EMAIL, fc.AADHAAR: c.AADHAAR, fc.ABHA_NUMBER: c.ABHA_NUMBER,
                   fc.ABHA_ADDRESS: c.ABHA_ADDRESS, fc.PAN: c.PAN, fc.MRN: c.MRN, fc.INSURANCE_ID: c.INSURANCE_ID,
                   fc.OTHER_ID: c.OTHER_ID}[cls]
            if cat == c.AADHAAR and re.search(r"[Xx*]{4}", value):
                cat = c.AADHAAR_MASKED
            action = c.PSEUDONYMIZE if cls == fc.MRN else c.REDACT
            return [_span(s0, e0, cat, action, "field", path, {"primary_id": cls == fc.MRN})]
        elif cls == fc.DOB:
            return [_span(s0, e0, c.DOB, c.SHIFT_DATE, "field", path, self._date_attrs(stripped, order))]
        elif cls == fc.DATE:
            if find_dates(stripped, order):
                return [_span(s0, e0, c.DATE, c.SHIFT_DATE, "field", path, self._date_attrs(stripped, order))]
            return self.detect_text(value, order, path)
        elif cls in (fc.AGE, fc.AGE_SEX):
            m = re.search(r"\d{1,3}", TextView.of(value).text)
            if m:
                view = TextView.of(value)
                a, b = view.span_to_original(m.start(), m.end())
                return [_span(a, b, c.AGE, c.GENERALIZE_AGE, "field", path, {"age": int(m.group(0))})]
            return []
        elif cls == fc.VILLAGE:
            return [_span(s0, e0, c.VILLAGE, c.GENERALIZE_LOCATION, "field", path)]
        elif cls == fc.PIN:
            m = re.search(r"\d{6}", TextView.of(value).text)
            if m:
                view = TextView.of(value)
                a, b = view.span_to_original(m.start(), m.end())
                return [_span(a, b, c.PIN, c.GENERALIZE_PIN, "field", path)]
            return []
        elif cls == fc.ADDRESS:
            view = TextView.of(value)
            extra = address_segments(view.text, 0, len(view.text))
            return self.detect_text(value, order, path, extra=extra)
        elif cls in (fc.GENDER, fc.TEHSIL, fc.DISTRICT, fc.STATE, fc.RELATION_VALUE):
            return []
        elif cls == fc.NAME_DOCTOR:
            view = TextView.of(value)
            guard = [c.SpanCandidate(0, len(view.text), c.DOCTOR, None, 0.9, c.TIER_PROTECTED, "doctor_field", c.KEEP)]
            return self.detect_text(value, order, path, extra=guard)
        if whole:
            return [_span(s0, e0, whole[0], whole[1], "field", path)]
        return self.detect_text(value, order, path, id_shapes=cls != fc.REFERENCE)

    def _date_attrs(self, value: str, order: str) -> dict:
        found = find_dates(value, order)
        if found and found[0][2] is not None:
            return {"date": found[0][2].isoformat(), "format": found[0][3]}
        return {"format": "unknown"}

    def _evidence(self, record, spans, classes, f) -> c.IdentityEvidence:
        ev = c.IdentityEvidence(record.record_id)
        values = {n.path: str(n.value) for n in record.fields if n.value is not None}
        if record.free_text:
            values[""] = record.free_text
        for s in spans:
            src = values.get(s.field_path)
            if src is None:
                continue
            surface = src[s.start:s.end].strip()
            if not surface:
                continue
            if s.category == c.PATIENT_NAME:
                ev.patient_names.append(surface)
            elif s.category == c.RELATIVE_NAME:
                ev.relative_names.append(surface)
            elif s.category in (c.AADHAAR, c.ABHA_NUMBER):
                ev.national_ids.setdefault(s.category, digits_only(surface))
            elif s.category in (c.PAN, c.EMAIL, c.ABHA_ADDRESS, c.INSURANCE_ID):
                ev.national_ids.setdefault(s.category, surface.upper() if s.category == c.PAN else surface.casefold())
            elif s.category == c.PHONE:
                d = digits_only(surface)
                if len(d) >= 10 and d[-10:] not in ev.phones:
                    ev.phones.append(d[-10:])
            elif s.category in (c.MRN, c.OTHER_ID):
                core = id_digit_core(TextView.of(surface).text)
                if core:
                    ev.scoped_ids.append(c.ScopedIdentifier(id_scope(surface), c.MRN, core))
            elif s.category == c.DOB and s.attrs.get("date") and not ev.date_of_birth:
                ev.date_of_birth = s.attrs["date"]
            elif s.category == c.AGE and "age" in s.attrs and ev.age is None:
                ev.age = s.attrs["age"]
            elif s.category == c.VILLAGE and not ev.village:
                ev.village = surface
        for n in record.fields:
            cls = classes.get(n.path)
            v = "" if n.value is None else str(n.value).strip()
            if not v:
                continue
            if cls == fc.GENDER and ev.gender is None:
                ev.gender = _GENDER.get(v.casefold())
            elif cls == fc.TEHSIL and ev.tehsil is None:
                ev.tehsil = v
            elif cls == fc.DISTRICT and ev.district is None:
                ev.district = v
            elif cls == fc.ORGANIZATION and ev.hospital is None and re.search(r"hospital|sadan|clinic", v, re.I):
                ev.hospital = v
        if ev.gender is None:
            for v in values.values():
                m = _GENDER_IN_AGE.search(v)
                if m:
                    ev.gender = _GENDER.get((m.group(1) or m.group(2)).casefold())
                    break
        return ev

    # ================================================================== hidden channels
    def _tag(self, value: str) -> str:
        d = hmac.new(self._filename_key, value.encode("utf-8"), hashlib.sha256).hexdigest()
        return d[:8]

    def sanitize_path(self, rel_path: str) -> str:
        """Same path if no component holds PII, else a PII-free, unique, deterministic path."""
        parts = rel_path.split("/")
        changed = False
        out = []
        for i, part in enumerate(parts):
            stem, dot, ext = part.rpartition(".") if i == len(parts) - 1 and "." in part else (part, "", "")
            clean = self._sanitize_component(stem)
            if clean != stem:
                changed = True
            out.append(clean + (dot + ext if dot else ""))
        if not changed:
            return rel_path
        last = out[-1]
        stem, dot, ext = last.rpartition(".") if "." in last else (last, "", "")
        out[-1] = f"{stem}_{self._tag(rel_path)}" + (dot + ext if dot else "")
        return "/".join(out)

    def _sanitize_component(self, text: str) -> str:
        extra = []
        view = TextView.of(text)
        for m in _FILE_NAME_PAIR.finditer(view.text):
            if trim_name(view.text, m.start(1), m.end(1)) and trim_name(view.text, m.start(2), m.end(2)):
                extra.append(c.SpanCandidate(m.start(), m.end(), c.PERSON_NAME, None, 0.7,
                                             c.TIER_EXPLICIT_IDENTITY, "filename_pair", c.REDACT))
        spans = [s for s in self.detect_text(text, ids_case_insensitive=True, extra=extra)
                 if s.action != c.KEEP and s.category not in (c.DATE, c.AGE)]
        if not any(s.reason_code not in WEAK_SOURCES for s in spans):
            return text
        clean = apply_placeholders(text, spans, style="filename")
        return re.sub(r"_{2,}", "_", clean).strip("_") or "file"

    def _strong_edits(self, text: str, accept_weak: bool = False) -> list[c.ResolvedSpan]:
        """Edits for a label-like string (header cell, key, file name). If only weak guesses
        fire ("Janm Tithi" read as a name), the string is left alone: renaming a header
        or key that holds no PII costs schema-preservation points. `accept_weak` is used
        for dictionaries keyed by data (see `_data_keyed`)."""
        spans = [s for s in self.detect_text(text, ids_case_insensitive=True)
                 if s.action != c.KEEP and s.category not in (c.DATE, c.AGE)]
        if not accept_weak and not any(s.reason_code not in WEAK_SOURCES for s in spans):
            return []
        return spans

    @staticmethod
    def _data_keyed(keys: list[str]) -> bool:
        """True if most keys look like entities (Title Case words, ID shapes), not schema
        names (snake_case / camelCase): such a dict is keyed by patient name or ID."""
        if len(keys) < 3:
            return False
        shape = re.compile(r"^(?:[A-Z][a-z]+(?:[ _][A-Z][a-z]+)+|[A-Za-z]{2,6}[/\-]?\d{4,}[/\-\d]*|[\u0900-\u097F ]+)$")
        return sum(bool(shape.match(k)) for k in keys) / len(keys) >= 0.5

    def sanitize_header(self, cells: list[str]) -> list[str]:
        out, seen = [], {}
        for cell in cells:
            spans = self._strong_edits(cell)
            new = apply_placeholders(cell, spans) if spans else cell
            if spans:
                seen[new] = seen.get(new, 0) + 1
                new = f"{new} {seen[new]}" if new in seen and seen[new] > 1 else new
            out.append(new)
        # make every renamed header unique and different from all originals
        counts: dict[str, int] = {}
        for x in out:
            counts[x] = counts.get(x, 0) + 1
        final, idx = [], {}
        for orig, x in zip(cells, out):
            if x != orig and counts[x] > 1:
                idx[x] = idx.get(x, 0) + 1
                x = f"{x} {idx[x]}"
            final.append(x)
        return final

    def sanitize_keys(self, keys: list[str]) -> dict[str, str]:
        """Old key -> new key for keys that hold PII (unique within the object)."""
        mapping, used = {}, set(keys)
        n = 0
        data_keyed = self._data_keyed(keys)
        for k in keys:
            spans = self._strong_edits(k, accept_weak=data_keyed)
            if not spans:
                continue
            cats = sorted({s.category for s in spans})
            n += 1
            new = f"redacted_{'_'.join(x.lower() for x in cats)}_{n}"
            while new in used:
                n += 1
                new = f"redacted_{'_'.join(x.lower() for x in cats)}_{n}"
            used.add(new)
            mapping[k] = new
        return mapping


def apply_placeholders(text: str, spans: list[c.ResolvedSpan], style: str = "text") -> str:
    """Development helper: apply spans with typed placeholders. Dates and ages are kept,
    PINs are reduced to their 3-digit prefix, payloads use their replacement."""
    out, pos = [], 0
    for s in sorted(spans, key=lambda x: (x.start, x.end)):
        if s.start < pos:
            continue
        out.append(text[pos:s.start])
        surface = text[s.start:s.end]
        if s.action == c.REENCODE and s.replacement is not None:
            rep = s.replacement
        elif s.action in (c.KEEP, c.SHIFT_DATE, c.GENERALIZE_AGE) and s.category != c.DOB:
            rep = surface
        elif s.category == c.PIN:
            d = digits_only(surface)
            rep = (d[:3] + "***") if len(d) == 6 else "[PIN]"
        else:
            rep = PLACEHOLDER.get(s.category, "[REDACTED]")
        if style == "filename":
            rep = rep.strip("[]").replace(" ", "-")
        out.append(rep)
        pos = s.end
    out.append(text[pos:])
    return "".join(out)
