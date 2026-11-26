# Anaam

Offline, CPU-only, LLM-free privacy firewall for multilingual hospital records.
Submission for Yugaantar DevForge, **Track 3: Secret Wards**.

## Status (read this first)

This repository currently holds the **detection and verification engine**. The pipeline that
reads input files, links patients, issues pseudonyms, shifts dates, generalises
quasi-identifiers and writes `sanitized/`, `report.json` and `records.jsonl` is **not in this
repository yet**, so there is no `main.py` and the official `check_submission.py --run` cannot
pass. `docs/COMPLIANCE_MATRIX.md` lists every requirement with its real status.

| Part | State |
|---|---|
| Unicode normalization, Devanagari to Latin transliteration, cross-script name keys | done, tested |
| Clinical Shield (medicines, doses, vitals, labs, diagnoses, doctors, wards) | done, tested |
| PII detection: names, relatives, phones, Aadhaar, ABHA, PAN, IDs, dates, ages, addresses | done, tested |
| Hidden channels: file names, CSV headers, JSON keys, base64 and escaped payloads | done, tested |
| Independent release verifier (fail-closed, rescrub then quarantine) | done, tested |
| Dev bench, chaos-data generator, repository identity audit | done |
| Patient linkage, HMAC pseudonyms, date shifting, age and location generalisation | not in this repo |
| Ingestion, serialisation, `report.json`, `records.jsonl`, `main.py` | not in this repo |

## Architecture

```
input files
  -> (pipeline) ingest, typed records ................ not yet in this repo
  -> DetectionEngine.prepare   harvest names, IDs, villages, ID templates from structured columns
  -> DetectionEngine.detect    clinical shield + identifiers + dates + addresses + names + lexicon
                               -> SpanResolver (direct ID > explicit name > date/age > clinical > weak)
  -> (pipeline) link, pseudonymise, shift, generalise ... not yet in this repo
  -> ReleaseGate.verify        known-value scan, residual scan, clinical loss, structure
                               -> RELEASE | rescrub once | QUARANTINE | ABORT (release-level only)
  -> sanitized/ + report.json + records.jsonl
```

## How detection works

No name list is needed to find a name. Rules read context: labels (`Name:`, `नाम:`, `Attendant:`),
relation markers (`S/o`, `W/o`, `C/O <name>`), honorifics (`ji`, `sahab`, `behenji`), time-log and
sender lines, and a name next to a postposition (`Anita ka BP`). Unseen names such as planted
canaries are found this way. A lexicon harvested from structured columns then finds the same
people elsewhere across scripts and spelling variants (Mohammad, Mohd, Md., मोहम्मद) using
transliteration and consonant-skeleton keys; single-token matches that rely only on the skeleton
are never redacted. Medical values are matched first and protected, so `Dolo 650 BD x 5 days`,
`1-0-1`, `BP 150/90`, `Dr. Ramesh` and `C/O fever` survive while `C/O Ramesh` does not.

## Declared models

None. Anaam uses rules, regular expressions, gazetteers and transliteration tables only.
No trained model, no pretrained weights, no LLM, no generative model, no network access.
Runtime code imports only the Python standard library.

## Security design (implemented parts)

The verifier never returns or logs matched text, only positions and reason codes. A file that
still fails after one rescrub is quarantined instead of released. Release-level failures abort:
unaccounted input, a report that disagrees with the output, the secret appearing anywhere, or
PII in the report or records. `docs/SECURITY.md` gives the threat model and the limits.

## Set-up and checks

```bash
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # Windows: .venv\Scripts
python -m pytest -q                                                     # 317 tests

# organiser kit lives in a SEPARATE checkout; it is never committed here
python tools/bench/run_bench.py --input ../Secret-Wards-ToolKit/dev/input --output out/bench
python tools/bench/score_dev.py --output out/bench --dev ../Secret-Wards-ToolKit/dev
python tools/chaos/generate.py --seed dev-1 --out out/chaos/dev-1
python tools/audit/scan_repo.py --truth ../Secret-Wards-ToolKit/dev/truth/truth.json
```

## Known limitations

- Measured results come from data the rules were written against; the chaos generator was
  written by the same author, so it only covers the variation that author imagined.
- Single common first names in running text ("Asha") rely on the lexicon or context; an unseen
  name with no context at all can be missed.
- Detection is rule-based; there is no learned model to adapt to new formats.
- Linkage, pseudonyms, date shifting and generalisation are not implemented here yet, so privacy
  against the organisers' attacker has not been measured.

See `docs/EVALUATION.md` for measured numbers and `docs/ASSUMPTIONS.md` for open decisions.
