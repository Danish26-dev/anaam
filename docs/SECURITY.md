# Security model

Describes the detection and verification engine (Danish). The pipeline's own controls (preflight,
key derivation, network guard, atomic publication, safe reason codes) are described in `README.md`
sections "Security design" and "Path and filename privacy". **The engine's controls below do not
protect the release until the engine is wired into `main.py`.**

## Assets

- Patient identities in the input: names, relatives, phones, national and hospital IDs, addresses.
- Quasi-identifiers: ages, dates, villages, PINs, rare diagnoses.
- `RAKSHA_SECRET`, which keys pseudonyms, date shifts and renamed paths.

## Attackers

1. The organisers' automated attacker: has a voter-style registry, partial known facts, and the
   sanitised release. Resistance is **not measured** yet (linkage, shifts and generalisation are not in this repo).
2. A reader of logs, temp files, the report and error messages.
3. A server breach: input, output, caches and temp files exposed. At-rest encryption is **not implemented**.

## Implemented controls

| Control | Where | Notes |
|---|---|---|
| Fail-closed file decision | `src/verify/release.py` | RELEASE, rescrub once, QUARANTINE, or ABORT for release-level breakage only |
| No values in diagnostics | `src/verify/*` | findings are positions plus reason codes such as `KNOWN_NAME`, `RESIDUAL_PHONE`; tested by `test_findings_never_contain_values` |
| Independent leak check | `src/verify/leaks.py` | known patient values searched in output, including inside base64, `\u` escapes, percent-encoding and HTML entities; detectors re-run on the output |
| Secret never in output | `ReleaseGate(secret=...)` | any output or report containing the secret aborts the release |
| Report and records scanned | `verify_release` | PII in `report.json` or `records.jsonl` aborts |
| Hidden channels | `src/detection/engine.py` | file names, CSV headers and JSON keys are renamed when they hold PII; tags are HMAC-keyed (`filename_key`) |
| No network code | stdlib only | static import audit; not yet tested in an isolated network namespace |
| No third-party runtime code | `requirements.txt` empty | nothing to supply-chain-attack at run time |
| No model or weights | n/a | nothing trained on data, nothing to extract |
| Repository hygiene | `.gitignore`, `tools/audit/scan_repo.py` | organiser truth, attacker files, outputs and secrets cannot be staged by accident; the audit prints counts only |

## Secret handling

The engine never reads `RAKSHA_SECRET` itself. The pipeline already derives purpose-separated keys
(`src/core/keys.py`: `pseudonym_key`, `date_shift_key`, `filename_key`, `temp_key`). When wired, it must
pass `filename_key` to `DetectionEngine(filename_key=...)` and the raw secret to `ReleaseGate(secret=...)`
so a leak of the secret into the release can be detected. The dev tools do not use a
secret and print only counts (`score_dev.py --show` prints practice surfaces and exists for synthetic
practice data only).

## Known limits and residual risks

- **Verifier blind spot:** it can only flag what a detector or the harvested lexicon can recognise.
  A name with no context, not harvested, and not in a structured column can be missed by both.
- **Structured files:** an ID-shaped token with no label is ignored by the verifier there (it would
  otherwise block bill numbers), so an unseen, unlabelled ID in a CSV or JSON value relies on column
  classification alone.
- **Generalisations are allowed through:** dates, ages, DOB, tehsil and district are not flagged by the
  verifier; the privacy layer owns them. A full 6-digit PIN is flagged unless `allow_full_pin` is set.
- **Re-identification:** rare diagnoses plus a narrow age band can still single out a person; not addressed here.
- **Date shifting:** a known original date of a re-identified patient would reveal that patient's offset;
  this is a property of any per-patient shift.
- **Not implemented:** encryption of intermediate data at rest, envelope keys, quarantine storage
  design, key rotation, and resource limits for hostile inputs (the 1,500-level JSON file is
  handled only by the dev bench's recursion limit and quarantine).
- Development was done on Windows. Under WSL Ubuntu the official `check_submission.py --run` passed
  (secret never written, input unchanged, keyed output); an isolated-network run was not done.
