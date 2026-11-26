# Compliance matrix

Status values: **DONE** (implemented and tested), **PARTIAL**, **NOT DONE**, **NOT MEASURED**.
"Pipeline" means Omkar's code, "engine" Danish's. Measurements are on the practice data unless a row
says otherwise (`docs/EVALUATION.md`). Nothing here is a claim about the hidden datasets.

## A. Environment and rules

| Requirement | Where | Evidence | Status |
|---|---|---|---|
| No runtime network | pipeline: in-process socket/DNS guard (`src/core/network_guard.py`); engine: stdlib only | static import audit; guard installed first in `main.py` | DONE. Not run in an isolated network namespace |
| CPU-only, no models | both | `requirements.txt` has no packages; README "Declared models: None" | DONE |
| No LLM / generative / large model | both | none imported; `check_submission.py`: no LLM packages | DONE |
| Nothing organiser-owned committed | `.gitignore`, `tools/audit/scan_repo.py` | `dev/`, truth, attacker files, outputs ignored | PARTIAL: the kit's three checker scripts are committed on `main` |
| No hardcoded practice identities | engine: 0 identity hits; pipeline: hits in 2 docstrings and 2 test files | `scan_repo.py` | PARTIAL: pipeline files to be cleaned |
| 2 CPUs / 4 GB / 15 min | | Linux: 16.5 s, 48.2 MB peak for 200 files | DONE (practice size) |
| Linux, Python 3.10+ | | WSL Ubuntu, Python 3.12.3: `check_submission.py --run` READY TO SUBMIT | DONE (3.10 itself not tested) |

## B. Detection (20 points)

| Requirement | Where | Evidence | Status |
|---|---|---|---|
| English, Hindi, Hinglish names; relatives | engine `names.py`, `identity_lexicon.py`, `transliteration.py` | `check_dev.py` via `main.py`: Latin, Devanagari, Hinglish 0.0% visible | DONE |
| Phones, Aadhaar, ABHA, PAN, MRN/UHID, insurance | engine `identifiers.py` | every category 0 of N visible | DONE |
| Doses, `1-0-1`, vitals not mistaken for IDs; `C/O fever`, `Dr.` kept | engine `clinical.py`, `span_resolver.py` | 4855 of 4855 medical values kept | DONE |
| Hidden: file names, headers, keys, metadata, base64 | engine `engine.py`, `attachments.py`; wired in writers and `main.py` | every hiding place 0.0% visible | DONE |
| Canaries | engine context rules | 0 of 4 found | DONE |
| Unseen formats and labels | engine `field_classifier.py` | sealed holdout seeds: 1 of 826 visible | PARTIAL: author-written held-out data |

## C. Medical preservation (20 points)

| Requirement | Where | Evidence | Status |
|---|---|---|---|
| Medicines, doses, frequencies, vitals, labs, diagnoses, procedures | engine `clinical*.py`; release gate blocks clinical loss | practice 4855/4855; holdout 302/302 | DONE |
| Exact stay intervals | pipeline `date_shift.py`; engine dates shifted by the same per-record offset | `tests/test_date_shift.py`, `tests/engine/test_integration.py` | DONE |
| Truthful age bands, village/PIN generalisation | pipeline `src/privacy/*` | `tests/test_json_generalize.py` | DONE *(pipeline tests)* |

## D. Identity consistency (15 points)

| Requirement | Where | Evidence | Status |
|---|---|---|---|
| Blocking, conflict-aware scoring, constrained clustering | pipeline `src/identity/*` with engine `IdentityEvidence` | `check_dev.py`: precision 0.97, recall 0.84, F0.5 0.94, 1 wrong merge | DONE on practice data |
| Linking on unseen formats | pipeline `find_patient_identity_column` | holdout: no pseudonyms issued | **NOT DONE** |
| HMAC pseudonyms written inside records | pipeline `pseudonyms.py`, writers | A6: 0 of 48 invertible | DONE |

## E. Privacy against attacks (25 points)

| Requirement | Where | Evidence | Status |
|---|---|---|---|
| Per-patient date shifts, age bands, location and PIN generalisation | pipeline `src/privacy/*` | A5 global shift not recoverable; A7 0 stable pseudonyms, 3.3% coincident dates | DONE |
| Profile re-identification | pipeline privacy layer | local A4: 51.0% of profiles | **PARTIAL**: highest remaining risk |
| Rare-condition handling | needs clinical risk flags | | NOT DONE |
| Local attacks A1, A3, A4, A5, A6, A7 | pipeline `tools/attack_lab/*` | re-run on the wired release (EVALUATION section 5) | DONE (measured) |

## F. Output quality and validity (10 points)

| Requirement | Where | Evidence | Status |
|---|---|---|---|
| Contract output, file accounting, quarantine | pipeline `main.py`, `src/export/*` | exit 0, 193 sanitized, 7 quarantined, CONTRACT OK | DONE |
| Release gate (rescrub, quarantine) | engine `src/verify/*`, called in `main.py` | 2 files re-scrubbed, 0 good files rejected | DONE |
| Valid FHIR with resolving references | pipeline `fhir_writer.py`; gate checks references | gate passes every FHIR output | DONE |
| No PII in logs, temp files, errors | atomic publish, safe reason codes, gate returns codes only | `check_submission.py`: secret never written, input unchanged | DONE |

## G. Speed and reliability (10 points)

| Requirement | Status |
|---|---|
| Determinism; a different secret changes output | DONE: `check_submission.py --run` under Linux |
| No crash on broken files | DONE: 7 quarantined, exit 0 |

## H. Submission checklist

| Item | Status |
|---|---|
| Public repository separate from the kit | `https://github.com/Danish26-dev/anaam` |
| `raksha.toml`, `requirements.txt`, `README.md`, `config/policy.yaml`, `main.py` | present |
| `validate_output.py` prints CONTRACT OK | DONE |
| `check_submission.py --run` prints READY TO SUBMIT | DONE under WSL Ubuntu |
| Detection engine wired into `main.py` | DONE (`feature/engine-wiring`, to be reviewed and merged) |
| Sealed holdout | PARTIAL: written by the detector's author |
| Two-page Project Brief PDF | draft at `docs/brief.pdf` (source `docs/BRIEF.md`); needs team review |
