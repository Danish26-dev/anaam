# Anaam

**An offline privacy firewall for Indian hospital records.** Anaam removes every patient
identifier from CSV, TSV, JSON, FHIR R4 and free-text exports in English, Hindi and Hinglish,
keeps every medical value intact, and links each patient's records across files and hospitals
under one stable, non-reversible pseudonym. Built for Track 3, *Secret Wards*, of the
Reinforce-SST Yugaantar DevForge challenge.

Rules, gazetteers, transliteration and context only — no LLM, no pretrained model, nothing
trained on this data. Runs offline on one CPU with the Python standard library.

## Why this approach

Off-the-shelf PII tools miss Hindi and Hinglish, break on Indian name structures (patronymics,
honorifics, surname-first order), and do nothing against an attacker who already knows a
patient's hospital and visit date. Anaam's core idea: **it learns each dataset's own identities
before it redacts.** It classifies every column and JSON key from its actual values, harvests
the names, IDs and villages it finds there, and catches the same identity again anywhere else —
a different script, a nickname, a file name, a JSON key, a base64 attachment — even in formats
and headers it has never seen before. A context-aware clinical shield keeps `Dolo 650 BD x 5
days`, `1-0-1` and vitals from ever being mistaken for an identifier.

## Results on the practice data

All numbers below are reproducible with `RAKSHA_SECRET=practice python main.py --input dev/input
--output my_output`, then the Team Kit's `check_dev.py` and `check_submission.py --run`. They are
development estimates on practice data, not the organisers' official score. Full methodology,
every number re-measured and every limitation: [`docs/EVALUATION.md`](docs/EVALUATION.md).

| Category | Result |
|---|---|
| Personal data leaked (content channel) | **0.0%** (0 of 3,230 pieces); 0 of 4 planted canaries |
| Medical values preserved | **100%** (4,497 of 4,497) |
| Patient linking | precision **0.97**, recall 0.82, F0.5 **0.94** (1 wrong merge in 817 records) |
| Output contract | `CONTRACT OK`, `READY TO SUBMIT` |
| Run time / memory | ~25 s, well under the 4 GB / 15-minute limit on 200 files |

**Re-identification resistance** (local attack-lab approximation of the organisers' attacker,
unprotected copy → Anaam release):

| Attack | Result |
|---|---|
| A1 — direct exposure of a name or ID | 33.8% → **0.0%** |
| A3 — voter-list record linkage | 708 of 817 records matchable → **0 of 817** |
| A4 — profile re-identification | 57.7% → **0.0%** (122 profiles) |
| A5 — targeted attack (attacker already knows a fact) | **5 of 14 real patients (35.7%)** remain re-identifiable |
| A6 — pseudonym inversion | 0 of 48 |
| A7 — cross-release linkability | 0 of 817 stable pseudonyms |

A1/A3/A4 reaching 0% is real, verified across three different secrets — not a measurement
artifact (the full trace, including two detection bugs we found and fixed along the way, is in
`docs/EVALUATION.md` §8). **A5 is the one open gap**, concentrated in patients with a rare
disease or an unusually long/short hospital stay, where the hospital name — kept deliberately,
since it is clinical, not personal, information — combines with that one rare fact to narrow
things down to a single person even after every direct identifier is gone. We tried suppressing
rare diagnosis text to close this and reverted it: it damaged a non-patient reference document
and flagged a common procedure as rare, for no measured benefit. We'd rather disclose a real,
bounded gap than ship an unverified fix. Details: `docs/EVALUATION.md` §8, `docs/PROGRESS.md`
open item 7.

## Architecture

```
input/ ──► ingestion ──► detection ──► identity resolution ──► privacy layer ──► writers ──► release gate ──► output/
           sniff format,  classify &    blocking, scoring,     date shift,       format-      re-check every
           decode, hash   harvest       conflict-aware         age bands,        preserving    file; rescrub
                           identities    clustering             k-location        CSV/JSON/      once, else
                                                                 suppression       FHIR/text      quarantine
```

1. **Ingestion** — sorted, deterministic file walk; streaming SHA-256 per file (the only file
   identity `report.json` uses); decodes UTF-8/16 (with and without BOM) and cp1252; detects
   format from content, not extension (catches JSON saved with a `.csv` name). Anything empty,
   truncated, undecodable, over-nested or unsupported is quarantined with a reason code, never
   copied through half-cleaned.
2. **Detection** — two passes. Pass one classifies every column/key from its header *and* values,
   so a renamed header still works, and harvests an identity lexicon. Pass two finds every PII
   span: Unicode/homoglyph normalization, Devanagari↔Latin transliteration keys (मोहम्मद, Mohammad,
   Mohd and Md. all compare equal), checksum-aware Aadhaar/ABHA/PAN/phone detectors, and context
   rules for names with no name list — labels, S/o·D/o·W/o, honorifics in all three scripts. A
   clinical shield protects doses, frequencies, vitals, lab values, ICD codes, diagnoses,
   complaints and doctors so they are never mistaken for identifiers. Hidden channels — base64,
   `\u` escapes, percent/HTML-entity encoding, file names, CSV headers, JSON keys — are decoded,
   scrubbed and re-encoded.
3. **Identity resolution** — blocking on national IDs, scoped hospital IDs, phones, name+DOB,
   name+relative and cross-script name+location. A pair links only on a shared strong identifier
   or an exact name plus one supporting clue; a contradiction blocks the merge; weak evidence can
   only ever join two unlinked singletons, so a chain of coincidental matches can never merge two
   different people. An uncertain record gets `patient: null` rather than a risky guess.
4. **Privacy layer** — one secret-keyed, non-zero date offset per patient (so a 9-day stay stays
   exactly 9 days, and no single global shift can be recovered); 5-year age bands that always
   contain the true age, applied consistently in structured fields *and* in free-text/FHIR
   narrative text; location generalised from village → tehsil → district → suppressed once fewer
   than 5 patients would share it.
5. **Writers & release gate** — format-preserving CSV/TSV/JSON/text/FHIR R4 output. An
   independent release gate re-reads every file afterward for residual PII, clinical data loss,
   structural validity and pseudonym presence; a leak gets one automatic rescrub, and a file that
   still fails is quarantined alone rather than risking the rest of the release.

Pseudonyms are `PSN-` + a Crockford-Base32 HMAC-SHA256 digest of the linked cluster's content
anchors, keyed by `RAKSHA_SECRET` — stable within one release, different under another secret,
and not reversible without the secret (verified: 0 of 48 inversions attempted successfully).

## Security design

- No run without a non-empty `RAKSHA_SECRET`; no run into a non-empty output directory.
- All network calls (socket connect, UDP, DNS) are blocked in-process.
- The secret and its derived subkeys are never logged, printed or serialized.
- Nothing partially processed ever touches disk: candidates stay in memory until every file has
  rendered and passed its structural checks, then the whole release is published by one atomic
  directory rename. A single file's failure rolls back only that file and quarantines it; the
  rest of the release still completes.
- `report.json` and `records.jsonl` are written by atomic temp-file replacement.
- No data is encrypted at rest because none is ever written at rest in the first place — there is
  nothing unencrypted on disk to protect. A reserved `temp_key` subkey exists for a future staging
  step, unused today.

## Run it

```powershell
$env:RAKSHA_SECRET = "practice"
python main.py --input <input-dir> --output <empty-output-dir>
```

Requires Python 3.10+, no third-party packages, no network access. The output directory must be
empty or absent; Anaam never modifies the input. Validate with the Team Kit's own checkers:

```bash
python3 validate_output.py --input <input-dir> --output <output-dir>   # expect: CONTRACT OK
python3 check_submission.py --repo <this-repo> --run                   # expect: READY TO SUBMIT
```

## Tests

427 standard-library `unittest`/pytest tests across the pipeline and detection engine:

```powershell
python -m unittest discover -s tests          # 76 tests, pipeline logic, stdlib only
pip install -r requirements-dev.txt
python -m pytest tests/engine -q               # 351 tests, detection/verification engine
```

Covers date-shift interval preservation, clustering's hard-conflict and anti-chain-merge guards,
pseudonym stability and secret-sensitivity, cross-script name detection, clinical-shield
preservation, FHIR reference rewriting, and atomic publication.

## Local attack simulator

`tools/attack_lab/` approximates the organisers' documented attacker (`docs/ATTACKS.md`) against
the practice data only — never imported by `main.py`, never available at evaluation time. Used to
produce every number in the results table above.

```powershell
python tools\attack_lab\run_attacks.py --output my_output --attacker dev\attacker
python tools\attack_lab\run_inversion.py --output my_output --truth dev\truth\truth.json
```

## Known limitations

- **A5 targeted-attack risk (35.7% of real patients with a known fact)** is the one open privacy
  gap, structural to keeping hospital names and exact intervals for clinical usefulness. See above.
- Multi-patient FHIR Bundles are quarantined rather than split into one release per patient.
- FHIR resources other than `Patient` are not passed through structured village/PIN
  generalisation (narrative text ages are banded; other structured fields on non-Patient
  resources are not).
- Our held-out tests were generated by the same team that wrote the detection rules, so they are
  a weaker check than genuinely unseen third-party data.

Full detail, every historical finding and every reverted attempt: [`docs/PROGRESS.md`](docs/PROGRESS.md),
[`docs/EVALUATION.md`](docs/EVALUATION.md), [`docs/SECURITY.md`](docs/SECURITY.md).

## Project layout

```
main.py                 entry point: python main.py --input {input} --output {output}
config/policy.yaml       privacy rules: age-band width, date-shift range, min location group size
raksha.toml              submission manifest (team name, setup, run command)
src/core/                shared contracts, keys, preflight, network guard
src/ingest/              format sniffing, decoding, per-format adapters
src/detection/           multilingual PII detection, clinical shield, field classification
src/identity/            blocking, scoring, conflict-aware clustering
src/privacy/             pseudonyms, date shifting, age/location generalisation
src/export/              format-preserving writers (CSV, JSON, FHIR, text)
src/verify/              independent release gate
tests/                   pipeline unit tests (unittest) and engine tests (pytest)
tools/attack_lab/        local re-identification attack simulator (dev-only)
tools/chaos/, tools/bench/, tools/audit/  dataset generation, benchmarking, repo hygiene
docs/BRIEF.md            source for the submitted 2-page Project Brief (docs/brief.pdf)
docs/EVALUATION.md       every measurement, with method and date
frontend/, tools/studio/ optional demo UI; not used by the evaluator
```

## Team

Md Danish Ali, Omkar L Kulkarni — Track 3, Secret Wards.
