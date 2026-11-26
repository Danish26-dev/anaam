# Compliance matrix

Status values: **DONE** (implemented and tested), **PARTIAL**, **NOT IN REPO** (belongs to the
pipeline that is not committed here), **NOT MEASURED**, **FAIL** (official check fails today).
Evidence refers to commands in `docs/EVALUATION.md`. Nothing here is a claim about the hidden data.

## A. Environment and rules

| Requirement | Module | Test / evidence | Status |
|---|---|---|---|
| No runtime network | stdlib only; no `socket`/`http`/`requests` imports (`urllib.parse` string helpers only) | import audit over `src/`, `tools/`, `tests/` | DONE (static). Not yet run under an isolated network namespace |
| CPU-only, no GPU | no numeric or ML libraries | `requirements.txt` has no packages | DONE |
| No LLM / generative / large model | none used | README "Declared models: None" | DONE |
| Synthetic data only | no data committed | `tools/audit/scan_repo.py` | DONE |
| No hardcoded practice identities | tests and tools use invented values | scan: identity=0 (gazetteer is a general list, 17% overlap) | DONE |
| 2 CPUs / 4 GB / 15 min | single-threaded | dev bench: 200 files in 7 to 13 s; memory **not measured** | NOT MEASURED |
| Python 3.10+ stdlib | | developed on 3.12, Windows | PARTIAL: Linux and 3.10 not yet run |

## B. Detection (20 points)

| Requirement | Module | Test | Status |
|---|---|---|---|
| English, Hindi, Hinglish names | `names.py`, `identity_lexicon.py`, `transliteration.py` | `test_names.py`, `test_identity_lexicon.py`, `test_transliteration.py` | DONE |
| Relatives (S/o, D/o, W/o, C/O, honorifics) | `names.py` | `test_names.py` | DONE |
| Phones, Aadhaar, ABHA, PAN, MRN/UHID, insurance | `identifiers.py` | `test_identifiers.py` | DONE |
| Doses, `1-0-1`, vitals not mistaken for IDs | `clinical.py` first, `span_resolver.py` | `test_clinical.py`, `test_span_resolver.py` | DONE |
| `C/O Ramesh` vs `C/O fever`, `Dr. Ramesh` kept | `names.py`, `clinical.py` | `test_names.py`, `test_clinical.py` | DONE |
| Hidden: file names, headers, keys, metadata, base64 | `engine.py`, `attachments.py` | `test_channels.py`, `test_attachments.py` | DONE (detection side) |
| Unseen formats and labels | `field_classifier.py` (value and header evidence) | chaos seeds dev-1..4 | PARTIAL: author-written test data only; no sealed holdout yet |
| Canaries | context rules, no list | 0 of 4 practice, 0 of 3 per chaos seed in output | DONE on available data |

## C. Medical preservation (20 points)

| Requirement | Module | Evidence | Status |
|---|---|---|---|
| Medicines, doses, frequencies, vitals, labs, units, diagnoses, procedures | `clinical*.py` | practice probes 4854/4855 (the one lost probe is absent from its own input row) | DONE |
| Exact hospital-stay intervals | date shifting | | NOT IN REPO |
| Truthful age bands | age generalisation | | NOT IN REPO |

## D. Identity consistency (15 points)

| Requirement | Status |
|---|---|
| Linkage, homonym protection, shared phones, hospital-scoped IDs, `patient: null` when unsure | NOT IN REPO. Detection supplies `IdentityEvidence`; no linker is committed |
| HMAC pseudonyms written inside records | NOT IN REPO |

## E. Privacy against attacks (25 points)

| Requirement | Status |
|---|---|
| Per-patient date shifts, age bands, location and PIN generalisation, rare-value handling | NOT IN REPO (policy stub in `config/policy.yaml`, not consumed) |
| Local attack simulation (A1, A3, A5) | NOT STARTED |
| Direct identifiers removed | DONE in detection; verified by `ReleaseGate` |

## F. Output quality and validity (10 points)

| Requirement | Module | Evidence | Status |
|---|---|---|---|
| Release gate: rescrub, quarantine, abort rules | `src/verify/*` | `test_verify.py`; verifier releases 194/194 of our output and flags 174/175 raw PII files | DONE |
| Contract output, honest report, file accounting | pipeline | `check_submission.py --run` exit code 2 (no `main.py`) | **FAIL** |
| Valid FHIR with resolving references | `structure.check_fhir_references` checks it; rewriting is the pipeline's | | PARTIAL |
| No PII in logs, temp files, errors | no value is printed by `src/`; verifier returns codes only | `test_findings_never_contain_values` | DONE for `src/`; pipeline NOT IN REPO |

## G. Speed and reliability (10 points)

| Requirement | Status |
|---|---|
| Determinism, different secret changes output | Detection and rename tags are deterministic (`test_channels.py`); end-to-end NOT MEASURED |
| No crashes on broken files | bench quarantines all 6 undecodable or unsupported files; pipeline NOT IN REPO |

## H. Submission checklist (from the governance directive)

| Item | Status |
|---|---|
| Public repository, separate from the kit | `https://github.com/Danish26-dev/anaam`, **nothing pushed yet** |
| `raksha.toml`, `requirements.txt`, `README.md`, `config/policy.yaml` | present |
| `main.py` supports the exact official command | **FAIL: missing** |
| `validate_output.py` prints CONTRACT OK | OK only for `tools/bench` output, which is not the submission entry point |
| `check_submission.py` prints READY TO SUBMIT | quick mode prints it, but quick mode checks files only. `--run` **FAILS** |
| Two-page Project Brief PDF | NOT STARTED (the checker warns) |
| No secrets, truth files or outputs committed | DONE (`.gitignore`, scan gate) |
