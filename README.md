# Anaam

Anaam is an offline privacy firewall for the Secret Wards privacy-engineering challenge. It reads heterogeneous hospital exports, removes or transforms identity-bearing data, preserves clinical values and formats, links records conservatively, and writes the evaluator contract:

```text
output/
├── sanitized/
├── report.json
└── records.jsonl
```

## Current integration status

Omkar's processing and privacy engine is implemented in this repository: preflight security, inventory and hashing, format detection/adapters, format-aware serialization, identity blocking/scoring/clustering, HMAC pseudonyms, date shifting, static generalization, report/manifest generation, and local A1/A3/A4/A5/A6/A7 attack tools.

Danish's detection engine is wired in through `src/detection/api.py`. It provides the clinical shield, multilingual PII detection, hidden channels and identity evidence. The independent release gate (`src/verify/`) checks every file before publication. On the practice data, `main.py` leaves 0 of 3,230 PII pieces visible, finds 0 of 4 canaries, keeps 4,855 of 4,855 medical values and links patients with F0.5 0.94. The official `check_submission.py --run` reports READY TO SUBMIT under Linux. Numbers, the held-out test and their limits: `docs/EVALUATION.md`. `src/detection/stub_detector.py` is no longer used.

## Requirements

- Python 3.10 or newer
- No runtime network access
- `RAKSHA_SECRET` set to a non-empty release secret
- No external Python packages are currently required

## Run

The official checkers ship with the Team Kit and are not copied into this repository. The commands
below assume the kit is cloned next to this repository as `../Secret-Wards-ToolKit` (set `KIT` to
another path if not).

PowerShell:

```powershell
$KIT = "..\Secret-Wards-ToolKit"
$env:RAKSHA_SECRET = "practice"
python main.py --input $KIT\dev\input --output my_output
python $KIT\validate_output.py --input $KIT\dev\input --output my_output
python $KIT\check_dev.py --output my_output
python $KIT\check_submission.py --repo . --run   # Linux or WSL; see docs/EVALUATION.md
```

Linux/macOS:

```bash
KIT=../Secret-Wards-ToolKit
RAKSHA_SECRET=practice python main.py --input $KIT/dev/input --output my_output
python3 $KIT/validate_output.py --input $KIT/dev/input --output my_output
python3 $KIT/check_dev.py --output my_output
python3 $KIT/check_submission.py --repo . --run
```

The output directory must be empty or absent. Anaam never modifies the input tree.

## Architecture

```mermaid
flowchart TD
    A[CLI and preflight] --> B[Sorted inventory and streaming SHA-256]
    B --> C[Encoding and content-based format detection]
    C --> D[CSV / TSV / JSON / text / FHIR adapters]
    D --> E[Detection integration seam]
    E --> F[IdentityEvidence]
    F --> G[Bounded candidate blocking]
    G --> H[Conflict-aware constrained clustering]
    H --> I[HMAC pseudonyms and date offsets]
    I --> J[Profile-consistent static privacy policy]
    J --> K[Format-aware candidate writers]
    K --> L[Independent verifier integration seam]
    L --> M[sanitized/ + report.json + records.jsonl]
```

### Shared contracts

`src/core/interfaces.py` contains the frozen contracts used by both halves of Anaam:

- `FileEnvelope`, `RecordEnvelope`, `FieldNode`
- `SpanCandidate`, `ResolvedSpan`
- `IdentityEvidence`, `ScopedIdentifier`, `ClusterAssignment`
- `FieldTransformation`, `TransformPlan`, `VerificationResult`

Raw identity evidence stays in memory and is never logged or written to the release. The live pipeline creates one `TransformPlan` per record; pseudonym, date offset, generalized-field edits, spans, and terminal status therefore share one integration contract.

## Ingestion and formats

- Input traversal is sorted by POSIX-style relative path for cross-platform determinism.
- Every file is hashed with streaming SHA-256; duplicate paths remain separate inventory entries.
- UTF-8, UTF-8 BOM, UTF-16 LE/BE, BOM-less UTF-16 with strong endian evidence, and cp1252 are supported.
- Embedded UTF-16 BOMs, malformed JSON, extreme nesting, empty files, and unsupported extensions fail closed.
- Content sniffing recognizes JSON hidden behind a `.csv` extension while preserving the original output path.
- Supported release formats are CSV, TSV, JSON, plain text, and single-patient FHIR R4 document Bundles.
- Unsupported XML, PDF, JPG, and multi-patient FHIR Bundles are quarantined rather than copied raw.

## Identity resolution

Candidate generation runs deterministic passes for:

1. national identifiers;
2. hospital-scoped MRN/UHID identifiers;
3. phone numbers;
4. canonical name plus DOB;
5. canonical name plus relative;
6. cross-script/upstream name variants plus location;
7. phonetic residual candidates.

High-frequency weak blocks are capped and skipped instead of creating quadratic work or unsafe merges. Strong-ID blocks use deterministic star expansion when large.

Pair scoring applies the published rule: link on a shared strong identifier, or an exact canonical name plus a supporting clue. Contradictory national/scoped identifiers are hard conflicts. Gender, age, location, and relative mismatches are recorded as soft conflicts. `PROBABLE` edges may only join singleton clusters, so weak evidence cannot propagate through an A-B-C bridge. Before every merge, all cross-cluster evidence is checked directly for hard conflicts, even if a pair never shared a blocking key.

Abstention is intentional: an unresolved record receives `patient: null` rather than a risky merge.
Danish's detection and verification engine is also in this repository: the clinical shield, multilingual PII detection, the identity lexicon, hidden-channel sanitisation and the independent release verifier (see [Detection and verification engine](#detection-and-verification-engine) below).

Identity evidence (names, relatives, national and scoped IDs, phones, DOB, age, gender, village) comes from the detection engine, which reads every field with its classified role. `main.py` calls the engine through `src/detection/api.py` (see `docs/INTERFACE_NOTES.md`).
## Pseudonyms

A linked cluster receives:

```text
fingerprint = SHA-256(sorted unique content anchors)
digest      = HMAC-SHA256(pseudonym_key, "patient-v1|" + fingerprint)
pseudonym   = "PSN-" + CrockfordBase32(digest)[:16]
```

Purpose-separated subkeys are derived from `RAKSHA_SECRET` for pseudonyms, date shifts, filename mapping, and optional temporary encryption. Exact duplicate files have distinct internal execution IDs but collapse to one content anchor for release identity, so adding a duplicate cannot change an existing pseudonym. Prefix collisions are detected and deterministically extended.

## Date shifting

- Every linked cluster receives one non-zero HMAC-derived offset.
- Unlinked records derive deterministic offsets from duplicate-insensitive content anchors.
- DD/MM/YYYY, DD/MM/YY, header-declared MM/DD/YYYY or MM/DD/YY, ISO dates, and FHIR date-times preserve their original syntax.
- CSV rows, JSON records, free text, and FHIR resources use per-record/patient offsets.
- A date mentioned inside ordinary free text -- a CSV notes cell, an unrecognized JSON string value, or FHIR narrative prose -- is shifted the same way a whole free-text document is, not only dates in a recognized date column/key.
- Admission/discharge intervals and cross-event ordering remain unchanged.
- A different release secret changes offsets.

## Static privacy policy

`config/policy.yaml` controls:

- five-year age bands;
- maximum date-shift range;
- minimum location group size.

CSV/TSV rows and JSON records (flat or nested, e.g. a registration record's `address.village`/`address.pin`) use one compatible plan per profile. Exact duplicate files do not inflate group counts. Location policy escalates from tehsil to district and then suppresses village, PIN, tehsil, and district when even district-level release is too rare. Generalized records are marked in `records.jsonl` and counted in `report.json`.

The CSV header-role table and the JSON key-role table share one lookup (`core.header_roles.role_for_header`), so a renamed column and a renamed JSON key are recognized identically. This table is a conservative, exact-match lookup, not a classifier. A column it does not recognise is handled by the detection engine's field classifier, which redacts a village or reduces a PIN instead of generalising it.

## FHIR handling

For single-patient R4 document Bundles Anaam:

- assigns the pseudonymous `Patient.id`;
- removes patient identifier, name, telecom, address, birth date, contact, photo, and link fields;
- removes `meta.source` values that may contain source MRNs/paths;
- rewrites patient references at any nesting depth;
- preserves opaque `urn:uuid` full URLs and resolvability;
- sanitizes indexed narrative text and every other non-structural string through the detection engine;
- shifts all recognized dates with one patient offset.

Bundles with zero or multiple Patient resources fail closed until per-patient Bundle partitioning is implemented.

## Path and filename privacy

Filename and directory components containing phone-number or scoped hospital-ID shapes are replaced by secret-keyed HMAC names while preserving file extensions. `report.json` identifies input files only by SHA-256 and declares the new output path; it never contains original filenames.

Before that mapping, the engine's `sanitize_path` removes names and identifiers from every path component and adds a keyed tag, so name-only file names are covered too.

## Security design

- Missing/empty secrets fail before the output directory is created.
- Input/output overlap and unsafe escaping symlinks are rejected.
- Non-empty output directories are rejected to prevent stale-release mixing.
- Python socket connect, UDP send, and DNS resolution are blocked in-process; the evaluator also denies network access externally.
- Errors exposed to stdout/stderr contain safe reason codes only.
- The secret and derived keys are never logged or serialized.
- Unsupported or malformed inputs are quarantined, never copied into `sanitized/`.
- A single file's rendering failure (a bad header, an unexpected structure, any unhandled exception) quarantines only that file. Anything it already queued in `records.jsonl`/`report.json` is rolled back first, so the rest of the release still completes instead of the whole run crashing.
- All candidate bytes remain in memory until every file has rendered and passed CSV/JSON/FHIR structural checks; the complete `sanitized/` tree is then published by directory rename.
- `report.json` and `records.jsonl` use atomic temporary-file replacement, and temporary files are removed on failure.
- Output filenames, reports, manifests, stdout, and stderr avoid raw input paths.

## Tests

A standard-library-only `unittest` suite covers the highest-risk logic: date-shift syntax/interval preservation and keying, identity clustering's hard-conflict and transitive-bridge guards, pseudonym order/duplicate insensitivity and secret-sensitivity, the shared header-role table, JSON/FHIR generalization and free-text date shifting, FHIR narrative indexing, and atomic candidate publication/structural validation.

```powershell
python -m unittest discover -s tests
```

No pytest or other third-party test runner is required.

## Local attack lab

These tools read practice-only attacker/truth files and are never imported by `main.py`:

```powershell
python tools\attack_lab\run_attacks.py --output my_output --attacker dev\attacker
python tools\attack_lab\run_inversion.py --output my_output --truth dev\truth\truth.json
python tools\attack_lab\run_cross_release.py --release-a release_a --release-b release_b
```

Implemented local measurements:

- A1 direct exposure, including output filenames;
- A3 record linkage with skip-empty filtering;
- A4 maximal profile aggregation through pseudonyms and surviving references;
- A5 known-facts matching and high-confidence global-shift recovery;
- A6 unkeyed pseudonym-transform inversion;
- A7 source-keyed cross-release pseudonym/date stability.

They are directional local measurements, not official scores.

## Determinism and measured pipeline checks

On the bundled 200-file practice dataset, Omkar's pipeline currently:

- prints `CONTRACT OK`;
- accounts for all 200 input files;
- sanitizes 193 and quarantines 7 malformed/unsupported files;
- preserves 4,855/4,855 medical probes when outputs are resolved using actual input hashes;
- produces byte-identical `sanitized/` and `records.jsonl` across same-secret runs;
- compares all 817 records across different-secret releases with zero unmatched records and zero stable pseudonyms;
- leaves 1.6% coincidentally stable date pairs in the local A7 approximation;
- copies zero unsupported files raw;
- passes `python -m unittest discover -s tests` (76 unit tests, standard library only).

These pipeline checks were measured before the engine was wired in. With the engine, the contract, file accounting and determinism results are the same (`docs/EVALUATION.md` section 7), and the local A7 approximation shows 3.3% coincidentally stable date pairs.

## Detection and verification engine

Implemented by Danish in `src/detection/` and `src/verify/`, with 335 tests in `tests/engine/`.
`main.py` calls it through `src/detection/api.py` (call order and span policy: `docs/INTERFACE_NOTES.md`).

| Module | What it does |
|---|---|
| `normalization.py`, `transliteration.py` | NFKC, zero-width, homoglyph, Indic-digit and diacritic folding with offsets mapped back to the original; Devanagari to Latin and cross-script name keys (Mohammad, Mohd, Md., मोहम्मद compare equal) |
| `clinical*.py` | Clinical Shield: medicines with dose, frequency and duration chains, vitals, labs with units, ICD codes, diagnoses, eponyms, procedures, complaints, history clauses, doctors, wards, hospitals |
| `identifiers.py`, `dates.py`, `address.py` | phones in every format, Aadhaar, ABHA, PAN, insurance and hospital IDs (labelled, shaped, learned templates), dates and ages, address components with a whitelist line classifier |
| `names.py` | context rules for names in English, Devanagari and Hinglish without a name list (labels, S/o W/o C/O, honorifics, time-log and sender lines), so unseen names and canaries are found |
| `identity_lexicon.py` | names, IDs and villages harvested from structured columns, then found again across scripts and spellings |
| `field_classifier.py` | classifies CSV columns and JSON keys from headers and values, so renamed headers still work |
| `span_resolver.py` | direct ID > explicit name > date or age > clinical protection > weak guess |
| `attachments.py`, `engine.py` | base64, `\u`, percent and HTML-entity payloads decoded, scrubbed and re-encoded; file names, CSV headers and JSON keys renamed only on strong evidence |
| `src/verify/` | independent release gate: known patient values (including inside payloads), residual detection, clinical loss, CSV/JSON shape, FHIR references, pseudonym presence; rescrub once, then quarantine; abort only on release-level breakage; findings carry codes, never values |

Measured through `main.py` with the official `check_dev.py`: 0 of 3,230 PII pieces visible on the practice data in Latin, Devanagari and Hinglish and in every hiding place, 0 of 4 canaries, 4,855 of 4,855 medical values. On two sealed held-out chaos seeds (unseen names, labels, ID shapes and date formats, run once with no tuning afterwards): 1 of 826 PII pieces visible and all medical values kept. Linking accuracy there is not measured (the generator writes no patient labels), and CSV/TSV records with unseen identity headers received no pseudonym. The generator was written by the same author as the rules, so it is a weaker test than third-party data. Details and limits: `docs/EVALUATION.md`.

Engine tests use pytest (`pip install -r requirements-dev.txt`, then `python -m pytest tests/engine -q`). The pipeline tests above still run with the standard library only.

## Known limitations
- Profile re-identification (local A4) is 51% of practice profiles. Raising `min_group_size` to 10 or 20 or widening age bands to 10 years did not change it, so the remaining risk comes from evidence the privacy layer does not yet generalise (likely dates, diagnoses and hospital combined).
- On unseen formats, CSV/TSV records get no pseudonym when `core.header_roles` does not recognise the patient-identity column (0 of 32 held-out CSV/TSV records; text and JSON records were pseudonymised). Linking accuracy on unseen formats is not measured yet, because the chaos generator writes no patient labels.
- Record-level rare-condition suppression depends on clinical risk flags from Danish's side and is not implemented.
- Multi-patient FHIR Bundles are quarantined rather than partitioned.
- FHIR resources other than `Patient` (e.g. a diagnosis/age-equivalent value on another resource type) are not passed through O10's age/village/PIN generalization; only CSV and JSON records are.
- `report.json` shows `peak_rss_mb: 0.0` on Windows (no `resource` module); on Linux it is measured (47 MB on the practice data).

## Release Studio (demo frontend)

A local product interface for the demo: a landing page (`/`) and a seven-screen research release
workspace, each screen with a Three.js view bound to the release's real results:

| Route | Screen |
|---|---|
| `/workspace` | Command Centre: release overview, next recommended action, operations queue |
| `/intake` | Source Intake: hospitals, files, formats, encodings, quarantine reasons |
| `/identity` | Identity Resolution: linked patients across sources, records released unlinked |
| `/protection` | Privacy Protection: placeholders, pseudonyms, renamed paths and keys, residual re-scan |
| `/clinical-integrity` | Clinical Integrity: clinical values before and after, by category |
| `/risk` | Privacy Risk: local attack lab, protected release vs an unprotected copy (practice data only) |
| `/assurance` | Release Assurance: seven verification layers and human authorisation |

It is optional: the evaluator runs only `main.py`, and nothing in the Studio changes the engine. Old
`/studio/*` links redirect to the new routes.

```bash
cd frontend && npm install && npm run build && cd ..          # once; needs Node 18+ (dev time only)
python tools/studio/evidence.py --holdout                     # optional: measured practice evidence
python tools/studio/server.py                                 # http://127.0.0.1:8765
```

- `tools/studio/server.py` (standard library) serves the built frontend and runs releases by calling
  the unchanged `main.py` as a subprocess. It binds to 127.0.0.1 only and rejects non-localhost Host
  headers, sends no CORS headers and sets a strict CSP. Uploaded inputs are deleted after each run,
  also on failure, and only released output, `report.json` and `records.jsonl` are served.
  `RAKSHA_SECRET` comes from its environment (or a random per-session value) and is never returned
  or logged.
- After `main.py`, the server runs the organiser's `validate_output.py` (from the kit folder), an
  independent residual re-scan, structure checks, a clinical before/after count and the release-wide
  check `verify.release.ReleaseGate.verify_release`. A release shows VERIFIED only if every check ran
  and passed.
- `tools/studio/evidence.py` measures the practice data with the organiser's checkers and the attack
  lab (also against an unprotected copy as the baseline) and writes counts only to
  `out/studio/evidence.json`, which is git-ignored.
- `tools/studio/record_demo.py` builds the **synthetic** demo workspace (`tools/studio/demo_data.py`:
  four fictional hospitals, five invented patients), runs the real CLI on it and records the
  result as `frontend/src/fixtures/demo-release.json`. Every screen labels its source: SYNTHETIC
  DEMO, PRACTICE EVALUATION or LOCAL RELEASE.
- `POST /api/inspect` runs the pipeline's own encoding, format and delimiter sniffers on a file
  before a release (in memory; nothing is written).
- The next recommended action comes from fixed rules in `frontend/src/state/actions.ts` over one
  derived release model (`frontend/src/state/model.ts`). No model or network is involved.
- Anaam never confirms a match, dismisses a finding or authorises a release by itself. A person
  records each review with a note, and authorisation requires every layer passed, every finding
  reviewed and an explicit confirmation. These decisions stay in the tab's memory only, never in
  browser storage, and are lost on reload.
- The frontend makes no third-party requests. It uses local system fonts, no analytics and no
  browser storage. File names typed by the user stay in the tab's memory. 3D views fall back to
  text without WebGL and stop animating under reduced motion.

## Submission configuration

`raksha.toml` is at the repository root:

```toml
[submission]
name  = "anaam"
setup = "pip install -r requirements.txt"
run   = "python main.py --input {input} --output {output}"
```
