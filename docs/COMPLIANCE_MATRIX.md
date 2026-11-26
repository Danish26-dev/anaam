# Compliance matrix

Status values: **DONE** (implemented and tested), **PARTIAL**, **NOT WIRED** (implemented, but `main.py`
does not use it yet), **NOT MEASURED**, **FAIL**. "Pipeline" means Omkar's code, "engine" Danish's.
Claims about the pipeline marked *(per pipeline README)* were measured by Omkar and not re-run by Danish.
Nothing here is a claim about the hidden datasets.

## A. Environment and rules

| Requirement | Where | Evidence | Status |
|---|---|---|---|
| No runtime network | pipeline: in-process socket/DNS guard (`src/core/network_guard.py`); engine: stdlib only, no network imports | static import audit (engine); guard *(per pipeline README)* | DONE. Not yet run in an isolated network namespace |
| CPU-only, no models | both | `requirements.txt` has no packages; README "Declared models: None" | DONE |
| No LLM / generative / large model | both | none imported | DONE |
| Synthetic data only, nothing organiser-owned committed | `.gitignore`, `tools/audit/scan_repo.py` | `dev/`, truth, attacker files, outputs ignored | PARTIAL: the kit's three checker scripts are committed on `main` (see `INTERFACE_NOTES.md`) |
| No hardcoded practice identities | engine: 0 identity hits; pipeline: hits in 2 docstrings and 2 test files | `scan_repo.py` | PARTIAL: pipeline files to be cleaned |
| 2 CPUs / 4 GB / 15 min | | `main.py`: 200 files, exit 0; peak memory **not measured** by us | NOT MEASURED |
| Linux, Python 3.10 | | developed on Windows, Python 3.12 | NOT MEASURED |

## B. Detection (20 points)

| Requirement | Where | Evidence | Status |
|---|---|---|---|
| English, Hindi, Hinglish names; relatives | engine `names.py`, `identity_lexicon.py`, `transliteration.py` | `tests/engine/test_names.py` and others | DONE, **NOT WIRED** |
| Phones, Aadhaar, ABHA, PAN, MRN/UHID, insurance | engine `identifiers.py` | `tests/engine/test_identifiers.py` | DONE, **NOT WIRED** |
| Doses, `1-0-1`, vitals not mistaken for IDs; `C/O fever`, `Dr.` kept | engine `clinical.py`, `span_resolver.py` | `tests/engine/test_clinical.py`, `test_span_resolver.py` | DONE, **NOT WIRED** |
| Hidden: file names, headers, keys, metadata, base64 | engine `engine.py`, `attachments.py`; pipeline renames phone / hospital-ID shaped path parts | `tests/engine/test_channels.py` | engine DONE, **NOT WIRED** |
| Unseen formats and labels | engine `field_classifier.py` | chaos seeds dev-1..4 | PARTIAL: author-written test data only |
| Released output today (`main.py` with the stub) | pipeline + stub | official `check_dev.py`: **73.9% of PII visible**, 4 of 4 canaries | **FAIL** until the engine is wired |
| Engine alone (dev runner) | `tools/bench/run_bench.py` | official `check_dev.py`: 0.0% visible, 0 of 4 canaries | DONE (not the submission path) |

## C. Medical preservation (20 points)

| Requirement | Where | Evidence | Status |
|---|---|---|---|
| Medicines, doses, frequencies, vitals, labs, diagnoses, procedures | engine `clinical*.py`; pipeline keeps values it does not touch | `main.py` (stub): 4855/4855; engine bench: 4855/4855 | DONE |
| Exact stay intervals | pipeline `src/privacy/date_shift.py` | `tests/test_date_shift.py` *(pipeline)* | DONE *(per pipeline README)* |
| Truthful age bands | pipeline `src/privacy/generalize.py` | `tests/test_json_generalize.py` *(pipeline)* | DONE *(per pipeline README)* |

## D. Identity consistency (15 points)

| Requirement | Where | Evidence | Status |
|---|---|---|---|
| Blocking, conflict-aware scoring, constrained clustering, `patient: null` on doubt | pipeline `src/identity/*` | `tests/test_clustering.py` *(pipeline)* | implemented |
| Real linking on practice data | needs engine `IdentityEvidence` | `main.py` (stub): precision 0, recall 0, because the stub returns empty evidence | **FAIL** until wired |
| HMAC pseudonyms written inside records | pipeline `src/privacy/pseudonyms.py`, writers | `tests/test_pseudonyms.py` *(pipeline)* | DONE *(per pipeline README)* |

## E. Privacy against attacks (25 points)

| Requirement | Where | Status |
|---|---|---|
| Per-patient date shifts, age bands, location and PIN generalisation | pipeline `src/privacy/*` | DONE *(per pipeline README)* |
| Rare-condition handling | pipeline needs clinical risk flags from the engine | NOT DONE |
| Local attacks A1, A3, A4, A5, A6, A7 | pipeline `tools/attack_lab/*` | implemented; not re-run by Danish |

## F. Output quality and validity (10 points)

| Requirement | Where | Evidence | Status |
|---|---|---|---|
| Contract output, file accounting, quarantine | pipeline `main.py`, `src/export/*` | `main.py` on practice data: exit 0, 193 sanitized, 7 quarantined, `validate_output.py` CONTRACT OK | DONE |
| Release gate (rescrub, quarantine, abort rules) | engine `src/verify/*` | `tests/engine/test_verify.py`; releases 194/194 of engine output, flags 174/175 raw PII files | DONE, **NOT WIRED** |
| Valid FHIR with resolving references | pipeline `src/export/fhir_writer.py`; engine `structure.check_fhir_references` | | DONE *(per pipeline README)*; check NOT WIRED |
| No PII in logs, temp files, errors | pipeline atomic publish and safe reason codes; engine returns codes only | `check_submission.py`: secret never written, input unchanged | DONE |

## G. Speed and reliability (10 points)

| Requirement | Status |
|---|---|
| Determinism, different secret changes output | DONE *(per pipeline README)*; `check_submission.py --run` could not confirm on Windows (see H) |
| No crash on broken files | `main.py` quarantines 7 files and exits 0 on practice data |

## H. Submission checklist

| Item | Status |
|---|---|
| Public repository separate from the kit | `https://github.com/Danish26-dev/anaam` |
| `raksha.toml`, `requirements.txt`, `README.md`, `config/policy.yaml`, `main.py` | present |
| `validate_output.py` prints CONTRACT OK on `main.py` output | DONE |
| `check_submission.py --run` prints READY TO SUBMIT | NOT VERIFIED: on Windows the checker splits paths that contain a space and `main.py` exits 2. Needs a Linux or WSL run |
| Detection engine wired into `main.py` | **NOT DONE**: the main blocker |
| Sealed holdout written by someone other than the detector's author | NOT STARTED |
| Two-page Project Brief PDF | NOT STARTED |
