# Interface notes for the pipeline (for Omkar)

How the detection and verification engine expects to be called. Everything here is implemented in
`src/detection/engine.py` and `src/verify/release.py` and covered by tests unless marked otherwise.

## Calling order

```python
engine = DetectionEngine(filename_key=keys.filename)   # bytes, derived from RAKSHA_SECRET
engine.prepare(files)                                   # list[FileEnvelope]; harvests names, IDs, villages
for f in files:
    new_path = engine.sanitize_path(f.relative_path)    # PII-free, unique, deterministic
    for rec in f.records:
        det = engine.detect_record(rec, f)              # -> RecordDetection(spans, evidence)
gate = ReleaseGate(engine, allowed_tokens=set(pseudonyms), secret=raksha_secret)
gate.prepare()
result = gate.verify_file(FileCandidate(text=..., fmt=..., original_text=..., pseudonyms=(...)))
```

`allowed_tokens` must contain every pseudonym issued, or the verifier flags them.

## Field and record conventions the adapters must follow

- CSV/TSV rows: `FieldNode.path = "col:<j>"`, `role_hint = header text`, locator `row:<i>`.
- JSON: `path` is the RFC 6901 pointer from the file root, `role_hint` the last key. Record locators are
  the pointers of list items, or `doc` for single objects and FHIR Bundles. Leaves outside list items
  use locator `@file` and must not be written to `records.jsonl`.
- Text notes: `RecordEnvelope.free_text`, locator `doc`.
- Spans are in **original string offsets** of the field value (the engine maps back from its normalised view).
- `ResolvedSpan.action` tells the writer what to do: `PSEUDONYMIZE` or `REDACT` (replace),
  `SHIFT_DATE`, `GENERALIZE_AGE`, `GENERALIZE_PIN`, `GENERALIZE_LOCATION` (privacy layer decides the value),
  `REENCODE` (use `span.replacement`, an already sanitised base64 or escaped payload), `KEEP` (do nothing).
  `attrs` carries parse hints without PII (`date` ISO value and format tag, `age`).

## Proposed additions to the agreed interfaces (need approval)

- `ResolvedSpan.field_path`, `.replacement`, `.attrs`.
- `ScopedIdentifier(scope, kind, value)` and `FieldTransformation(field_path, action, params)` were referenced
  by the plan but never defined; minimal definitions are in `src/contracts.py`.
- `VerificationResult.findings` (positions and categories only).

## Things the pipeline still has to do

Ingestion and quarantine of unsupported files; linkage; pseudonyms inside records; date shifting;
age, location and PIN generalisation; FHIR rewriting with resolvable references; `report.json`,
`records.jsonl`; deterministic ordering and counts that match the exported tree.
