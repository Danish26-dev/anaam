# Integration guide: pipeline + detection engine

The two halves are connected on branch `feature/engine-wiring`. `main.py` calls the detection engine
through `src/detection/api.py` and runs the release gate (`src/verify/`) on every file before
publication. `src/core/interfaces.py` is the only contract.

## Who owns what

| Area | Owner | Location |
|---|---|---|
| Preflight, keys, network guard, ingestion, adapters, writers, identity resolution, pseudonyms, date shifting, generalisation, report, records, attack lab | Omkar | `main.py`, `src/core`, `src/ingest`, `src/export`, `src/identity`, `src/privacy`, `tools/attack_lab`, `tests/*.py` (unittest) |
| Normalization, transliteration, clinical shield, PII detection, identity lexicon, field classifier, span resolver, hidden channels, release verifier, dev bench, chaos generator, repo audit | Danish | `src/detection/*` (except `stub_detector.py`), `src/verify`, `tools/bench`, `tools/chaos`, `tools/audit`, `tests/engine` (pytest) |
| Integration seam | shared | `src/detection/api.py`, and the writer call sites listed below |

## Call order in `main.py`

```python
configure_detection(keys.filename_key)        # after preflight
# ... ingest every file into FileEnvelopes (unchanged) ...
failures = prepare_detection(envelopes)       # harvest over ALL files, then detect every record
#   a file whose detection fails is quarantined alone
out_rel = resolve_output_relative_path(key, sanitize_path(rel))   # engine first, then the mapper
evidence = extract_identity_evidence(record)  # engine evidence -> cluster_records
# ... clustering, pseudonyms, date offsets, generalisation (unchanged) ...
render_csv(..., record_ids_by_row)            # writers get record ids for per-field spans
render_json_records(..., record_ids_by_locator) / render_json_doc(..., record_id)
render_fhir_bundle(..., record_id=...)        # now cleans every non-structural string
render_text_document(..., record_id)
ReleaseGate(engine, allowed_tokens=pseudonyms, secret=...).verify_and_fix(...)
#   leak -> one re-scrub; still failing or verifier crash -> that file is quarantined
```

Detection moved after ingestion because the harvest pass needs every file before any record is
detected.

## Span policy (`src/detection/api.py`)

- Per-field spans are used only while the writer holds the field's original value. If the pipeline
  rewrote the value (generalised village, embedded pseudonym, duplicate header), the value is scanned
  on its own with the harvested lexicon. Issued pseudonyms (`PSN-...`) are exempt from that scan.
- Whole-field age, village and PIN spans are dropped when `core.header_roles.role_for_header`
  recognises the column, because the privacy layer generalises those truthfully, and kept village
  or banded age earns utility. A column the pipeline does not recognise (for example a village column
  headed `City`) stays with the engine, which redacts the village or reduces the PIN to 3 digits.
- Dates and DOBs found by the engine (`SHIFT_DATE`) are shifted by the record's offset in the writer,
  keeping separator, field order and widths (`export/text_writer._shift_like`). A DOB that cannot be
  shifted is redacted. The regex date pass is skipped for those values so a date is never shifted twice.
- `REDACT` and `PSEUDONYMIZE` become typed placeholders; `REENCODE` uses `span.replacement` (sanitised
  base64 / escaped payloads); `KEEP` is untouched.
- JSON numbers that hold an identifier (an Aadhaar stored as a number) become `0`, keeping the type.
- CSV header cells go through `sanitize_header`, JSON keys through `sanitize_keys`; both rename only on
  strong evidence, so schema names are kept.

Path conventions: CSV fields are `col:<Header>`; JSON array-item fields are pointers relative to the
item (`/patient_name`); document JSON and FHIR fields are pointers from the file root; text uses
`free_text` with field path `""`.

## Changes made in Omkar's files for the wiring

- `main.py`: detection after ingestion; record ids passed to writers; release gate before publication;
  a latent `KeyError` fixed (JSON plans were looked up after the pseudonym had been cleared, which
  only happens once records are linked).
- `src/export/*_writer.py`: optional record-context parameters, header/key sanitisation, the FHIR
  string pass, numeric identifiers. Existing call shapes still work; all 76 unittest tests pass.

`src/detection/stub_detector.py` is unused and can be deleted.

Omkar wired the engine independently on `main` (`b8aca73`, `89576e5`). Measured on the practice data,
that version quarantined 49 files (the verifier false positives fixed on this branch), left 1.5% of
PII visible (27.1% in file names, from the quarantined files) and linked with F0.5 0.56. The merge
kept this branch's wiring and took his `check_json_shape` fix, `KeySet.secret_text()` (now used for
the gate's secret check) and `src/export/verification.py`. That module is not called yet. It builds
richer verifier inputs (original JSON, exempt generalisation prefixes) and a release-level check
before publication, and it is the next step for the JSON shape check.

## Open points for the team

This list is from the original engine-wiring merge; later status for each is noted below rather
than rewritten, so this stays a record of what the integration looked like at that point.

- ~~**Linking on unseen formats (Omkar):** on the held-out seeds, CSV/TSV records got no
  pseudonym~~ fixed: `detection.api.identity_column()` / `identity_key_path()` fall back to the
  engine's field classifier when the fixed header/key tables find no identity column. Verified
  0/8 -> 8/8 (CSV) and 0/8 -> 6/8 (TSV) on generated unseen-header samples. See `docs/PROGRESS.md`.
- ~~**A4 profile re-identification at 51%**~~ re-measured at 0.0% locally: the figure traced almost
  entirely to local attack-tool measurement bugs (a bare-digit substring match, a missing
  word-boundary on name matching) plus one real detection gap (an unlabeled two-word name whose
  second word was a generic Indian name-part, e.g. "Shabana Bano", released half-redacted). All
  fixed; see `docs/EVALUATION.md` §8. **A5 (targeted attack) is the current largest known gap**:
  5 of 14 real patients with a known fact (35.7%), concentrated in hospital + rare-condition/
  stay-length combinations, after separating genuine hits from decoy and wrong-person coincidences
  the local tool originally counted the same way.
- ~~**Kit scripts are committed on `main`**~~ removed in the Release Studio merge; kept locally only
  for self-checking per `docs/SPEC.md` §8, not part of this repository.
- ~~**Practice-data values in pipeline files**~~ fixed; the audit now reports `identity=0`.
- **Windows:** `check_submission.py --run` fails when the path has a space; run it under WSL (see
  `docs/EVALUATION.md` section 7). Use `git config core.autocrlf false` in every clone.
