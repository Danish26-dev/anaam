# Integration guide: pipeline + detection engine

Both halves are now in one tree on `main`, but **they are not connected**. `main.py` still calls the
regex stub through `src/detection/api.py`. This page lists exactly what has to change to connect them,
verified against the code on both sides (merge commit `eace4a7`).

## Who owns what

| Area | Owner | Location |
|---|---|---|
| Preflight, keys, network guard, ingestion, adapters, writers, identity resolution, pseudonyms, date shifting, generalisation, report, records, attack lab | Omkar | `main.py`, `src/core`, `src/ingest`, `src/export`, `src/identity`, `src/privacy`, `tools/attack_lab`, `tests/*.py` (unittest) |
| Normalization, transliteration, clinical shield, PII detection, identity lexicon, field classifier, span resolver, hidden channels, release verifier, dev bench, chaos generator, repo audit | Danish | `src/detection/*` (except `api.py`, `stub_detector.py`), `src/verify`, `src/contracts.py`, `tools/bench`, `tools/chaos`, `tools/audit`, `tests/engine` (pytest) |
| Integration seam | shared | `src/detection/api.py` |

## Incompatibilities that block wiring

### 1. Two interface files

`src/core/interfaces.py` (pipeline) and `src/contracts.py` (engine) define the same dataclasses.
Agreed direction: keep `src/core/interfaces.py` as the single file, delete `src/contracts.py`.

| Dataclass | Pipeline | Engine | Effect |
|---|---|---|---|
| `FieldNode`, `RecordEnvelope`, `FileEnvelope`, `SpanCandidate`, `IdentityEvidence`, `ClusterAssignment`, `TransformPlan` | same fields | same fields | compatible |
| `ResolvedSpan` | `start, end, category, action, reason_code` | adds `field_path`, `replacement`, `attrs` | additive; writers must read `replacement` and `attrs` |
| `ScopedIdentifier` | `system, value` | `scope, kind, value` | **breaking**: `src/identity/blocking.py` and `scoring.py` read `.system` |
| `FieldTransformation` | `path, action, replacement` | `field_path, action, params` | **breaking**: every `FieldTransformation(...)` call in `main.py` |
| `VerificationResult` | no `findings`, `retry_allowed=True` default | adds `findings: list[LeakFinding]`, default `False` | additive |

### 2. Span action names (breaking, easy to miss)

| Pipeline expects | Engine emits | What the engine means |
|---|---|---|
| `"redact"` | `REDACT` | replace with a typed placeholder |
| (none) | `PSEUDONYMIZE` | replace a patient name or primary ID with the record's pseudonym |
| `"generalize"` | `SHIFT_DATE`, `GENERALIZE_AGE`, `GENERALIZE_LOCATION`, `GENERALIZE_PIN` | the privacy layer decides the new value |
| (none) | `REENCODE` | use `span.replacement`, an already sanitised base64 / `\u` / percent / HTML payload |
| `"preserve"` | `KEEP` | do nothing |

`stub_detector.apply_resolved_spans` acts only on `action == "redact"`. Passed the engine's spans
unchanged, it would replace nothing and every value would pass through. One vocabulary must be chosen
and both sides mapped to it.

### 3. Hidden channels need writer calls

The engine cleans these through methods, not through spans on content fields:

- `DetectionEngine.sanitize_path(rel_path)` for file and folder names (HMAC-keyed tag, deterministic);
- `DetectionEngine.sanitize_header(cells)` for CSV header cells;
- `DetectionEngine.sanitize_keys(keys)` for JSON object keys (returns old -> new);
- `REENCODE` spans for base64 and escaped payloads.

With the stub today, base64, metadata, key and header PII are 100% visible in `main.py` output
(official `check_dev.py`, practice data).

### 4. Import layout (Danish's side to fix)

The pipeline puts `src/` on `sys.path` and imports `core`, `detection`, `identity` as top-level packages.
The engine uses relative imports such as `from .. import contracts`, which assume `src` is a package,
so `import detection.engine` fails under the pipeline's layout with "attempted relative import beyond
top-level package". The engine will switch to the pipeline's layout.

## Calling order once connected

```python
engine = DetectionEngine(filename_key=keys.filename_key)   # derived from RAKSHA_SECRET by core.keys
engine.prepare(file_envelopes)                              # harvest pass over ALL files first
for f in file_envelopes:
    out_path = engine.sanitize_path(f.relative_path)
    for rec in f.records:
        det = engine.detect_record(rec, f)                  # -> spans (original offsets) + IdentityEvidence
gate = ReleaseGate(engine, allowed_tokens=set(issued_pseudonyms), secret=raksha_secret)
gate.prepare()
result = gate.verify_file(FileCandidate(text=..., fmt=..., original_text=..., pseudonyms=(...)))
```

`allowed_tokens` must contain every pseudonym issued, or the verifier flags them as unknown tokens.

Adapter conventions the engine expects: CSV fields `path="col:<j>"` with `role_hint` = header text; JSON
fields use RFC 6901 pointers from the file root; record locators `row:<i>`, JSON item pointers, `doc`;
leaves outside list items use locator `@file` and must not be written to `records.jsonl`. The pipeline's
`FieldNode.path` comment uses `"col:Mobile"`, a header name, not an index: **one more thing to agree**.

## Agreed order of work

1. Omkar reconciles `src/core/interfaces.py` and his call sites (fields above, the action vocabulary,
   `replacement` handling) and pushes to `main`. Danish does not touch `main` meanwhile.
2. Danish merges that `main` into `feature/anaam-engine`, deletes `src/contracts.py`, switches to the
   pipeline's import layout, maps actions, and implements the bodies of `src/detection/api.py` with the
   engine. Runs `unittest` (76), `pytest tests/engine` (317) and the kit's checkers.
3. Merge to `main` through a pull request reviewed by the other person. No force-push, no rebase of
   pushed branches.

## Other findings for the team

- **Kit scripts are committed on `main`:** `check_dev.py`, `check_submission.py`, `validate_output.py`.
  The governance directive says not to commit the Team Kit; decide whether to remove them.
- **Practice-data values in pipeline files** (found by `tools/audit/scan_repo.py`): example values in
  docstrings of `src/identity/canonicalize.py` and `src/privacy/generalize.py`, and practice names,
  Aadhaar, DOB, PIN and village values in `tests/test_clustering.py` and `tests/test_json_generalize.py`.
  The kit's static audit flags hard-coded dev identifiers, so these should be replaced with invented values.
- **`check_submission.py --run` cannot pass on Windows with a path containing a space.** It quotes paths
  with POSIX single quotes (`shlex.quote`), which `cmd` does not understand, so `main.py` receives a split
  argument and exits 2. This is a tool limitation, not a pipeline bug. Run it under Linux or WSL.
- **Line endings:** Windows Git with `core.autocrlf=true` rewrites the kit's practice files, changing
  172 of 200 SHA-256 values. Use `git config core.autocrlf false` in every clone.
