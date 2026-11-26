# Integration guide: pipeline + detection engine

Both halves are now in one tree on `main`, but **they are not connected**. `main.py` still calls the
regex stub through `src/detection/api.py`. This page lists what has to change to connect them,
verified against the code on both sides after Omkar's contract reconciliation (`e4727c2`) was merged.

## Who owns what

| Area | Owner | Location |
|---|---|---|
| Preflight, keys, network guard, ingestion, adapters, writers, identity resolution, pseudonyms, date shifting, generalisation, report, records, attack lab | Omkar | `main.py`, `src/core`, `src/ingest`, `src/export`, `src/identity`, `src/privacy`, `tools/attack_lab`, `tests/*.py` (unittest) |
| Normalization, transliteration, clinical shield, PII detection, identity lexicon, field classifier, span resolver, hidden channels, release verifier, dev bench, chaos generator, repo audit | Danish | `src/detection/*` (except `api.py`, `stub_detector.py`), `src/verify`, `tools/bench`, `tools/chaos`, `tools/audit`, `tests/engine` (pytest) |
| Integration seam | shared | `src/detection/api.py` |

## Resolved: one interface file (Omkar, `e4727c2`)

`src/core/interfaces.py` is the single contract. `src/contracts.py` is now a re-export shim so the
engine's `c.X` references keep working; add nothing to it. Decisions recorded in the module docstring:

| Dataclass | Resolution |
|---|---|
| `ScopedIdentifier` | engine shape `scope, kind, value`; `src/identity/blocking.py` and `scoring.py` updated |
| `ResolvedSpan` | gained `field_path`, `replacement`, `attrs`; writers must read `replacement` for `REENCODE` |
| `FieldTransformation` | pipeline shape `path, action, replacement` kept |
| `VerificationResult` | gained `findings: list[LeakFinding]` |
| channel / action / category / tier constants | engine vocabulary adopted |

## Still blocking wiring

### 1. Span action names in the stub (breaking, easy to miss)

The contract now defines the engine's upper-case actions, but `stub_detector.py` still emits and checks
lower-case `"redact"`, and `ResolvedSpan.action`'s comment in one place still lists
`"redact" | "generalize" | "preserve"`. The mapping:

| Pipeline expects | Engine emits | What the engine means |
|---|---|---|
| `"redact"` | `REDACT` | replace with a typed placeholder |
| (none) | `PSEUDONYMIZE` | replace a patient name or primary ID with the record's pseudonym |
| `"generalize"` | `SHIFT_DATE`, `GENERALIZE_AGE`, `GENERALIZE_LOCATION`, `GENERALIZE_PIN` | the privacy layer decides the new value |
| (none) | `REENCODE` | use `span.replacement`, an already sanitised base64 / `\u` / percent / HTML payload |
| `"preserve"` | `KEEP` | do nothing |

`stub_detector.apply_resolved_spans` acts only on `action == "redact"`. Passed the engine's spans
unchanged, it would replace nothing and every value would pass through. The replacement for the stub
in `src/detection/api.py` must apply the upper-case actions.

### 2. Hidden channels need writer calls

The engine cleans these through methods, not through spans on content fields:

- `DetectionEngine.sanitize_path(rel_path)` for file and folder names (HMAC-keyed tag, deterministic);
- `DetectionEngine.sanitize_header(cells)` for CSV header cells;
- `DetectionEngine.sanitize_keys(keys)` for JSON object keys (returns old -> new);
- `REENCODE` spans for base64 and escaped payloads.

With the stub today, base64, metadata, key and header PII are 100% visible in `main.py` output
(official `check_dev.py`, practice data).

### 3. Import layout (Danish's side to fix)

The pipeline puts `src/` on `sys.path` and imports `core`, `detection`, `identity` as top-level packages.
The engine uses relative imports such as `from .. import contracts`, which assume `src` is a package.
Re-checked after the reconciliation: `import detection.engine` with `src/` on the path still fails with
"attempted relative import beyond top-level package". The shim fixes the other direction only. The
engine will switch to `from core import interfaces as c`.

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

1. Done: Omkar reconciled `src/core/interfaces.py` and the identity call sites (`e4727c2`), and that
   `main` was merged into the engine branch.
2. Danish switches the engine to the pipeline's import layout, then deletes the `src/contracts.py` shim,
   maps actions, and implements the bodies of `src/detection/api.py` with the engine. Runs `unittest`
   (76), `pytest tests/engine` (317) and the kit's checkers.
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
