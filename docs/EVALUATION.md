# Evaluation record

All numbers were produced in this workspace by the commands shown. They are development
estimates, **not** the organisers' score. The organisers' hidden datasets, attacker and evaluator
are not available to us.

## 1. Baseline: the organiser starter, unchanged

`python Secret-Wards-ToolKit/starter/main.py` on the practice data, then the official `check_dev.py`:

| Measure | Starter |
|---|---|
| contract | CONTRACT OK |
| personal data still visible | 2718 of 3230 pieces (84.1%); latin 82.8%, Devanagari 100%, Hinglish 100% |
| planted canaries leaked | 4 of 4 |
| medical values kept | 4855 of 4855 |
| patient linking | none (precision 0, recall 0) |

## 2. Current dev bench (detection engine only, no linkage)

`tools/bench/run_bench.py` is a development runner, **not** the submission entry point.
Official `validate_output.py` and `check_dev.py` on its output:

| Measure | Dev bench |
|---|---|
| contract | CONTRACT OK |
| personal data still visible | 0 of 3230 (0.0%) in latin, Devanagari and Hinglish; 0.0% in content, filename, base64, metadata, key, header |
| planted canaries leaked | 0 of 4 |
| medical values kept (official self-check) | 4855 of 4855 |
| patient linking | not implemented (0) |
| raw copies of broken files | 0 |

Our stricter estimate, `tools/bench/score_dev.py` (token- and record-level, modelled on `docs/SCORING.md`):
recall 1.0000 for every PII type, script and channel; clinical probes 4854/4855; non-PII token
retention 0.9976; all 10 meaning-trap groups preserved (1-0-1 428/428, doctor 208/208,
c/o-complaint 78/78, k/c/o 62/62, h/o 57/57, dose 47/47, hospital-ward 27/27, eponym 21/21,
doctor-vs-relative 7/7, asha 2/2). The single lost probe, "oxygen given en route", does not occur in
its own input row, so it is a data quirk, not a leak or a loss.

Release verifier on the same data (`tools/bench/verify_bench.py`): sanitized output released 194/194;
raw input files containing PII flagged 174/175 (the one released is a README with no PII);
clean documents released 4/4.

Run time for 200 files was 7 to 13 s across runs on this laptop. Peak memory was not measured.

## 3. Generalisation: chaos datasets

`tools/chaos/generate.py` builds synthetic datasets with names, headers, ID shapes and date formats not
in the practice data, with its own answer key, scored by the same `score_dev.py`.

| Seed | PII recall (weighted macro) | clinical probes kept | non-PII token retention | canaries leaked | verifier released |
|---|---|---|---|---|---|
| dev-1 | 1.0000 | 154/154 | 0.9817 | 0 of 3 | 43/43 |
| dev-2 | 1.0000 | 151/151 | 0.9761 | 0 of 3 | 42/42 |
| dev-3 | 1.0000 | 151/151 | 0.9813 | 0 of 3 | 42/42 |
| dev-4 | 1.0000 | 148/148 | 0.9784 | 0 of 3 | 41/41 |

What this does and does not show:

- The first run on dev-1 found real gaps (HOUSE recall 0.53 for "Plot 723"; villages on a
  "Residence:" line), which were fixed. Later fixes (digit groups across line breaks, tab as a label
  gap, header renames) came from the verifier on these seeds. So **no seed is an untouched test**.
- One author wrote the detector and the generator, so the generator only covers variation that
  author imagined. The organisers' reference lost about 34 points from normal to unseen-format data.
  A sealed holdout, written by a different person with different templates, is still to be built.

## 4. Repository audit

`tools/audit/scan_repo.py` against the practice answer key: identity findings 0, blocked files 0,
generic findings 128 (single common first names and generic address words). The general name
gazetteer has 447 entries, of which 76 (17%) appear in the practice data; it is used only to
profile column values, not to decide redaction.

## 5. The submission entry point (`main.py` with the engine wired in)

`main.py` runs the detection engine through `src/detection/api.py` and the release gate before
publication (branch `feature/engine-wiring`). Practice data, `RAKSHA_SECRET=practice`, official
`check_dev.py`:

| Measure | Before wiring (regex stub) | After wiring |
|---|---|---|
| exit code, files | 0; 193 sanitized, 7 quarantined | 0; 193 sanitized, 7 quarantined (the broken inputs only) |
| contract (`validate_output.py`) | CONTRACT OK | CONTRACT OK |
| personal data still visible | 2387 of 3230 (73.9%) | **0 of 3230 (0.0%)**; Latin, Devanagari, Hinglish all 0.0% |
| by hiding place | base64 / metadata / key / header 100% | content, filename, base64, metadata, key, header all 0.0% |
| planted canaries leaked | 4 of 4 | **0 of 4** |
| medical values kept | 4855 of 4855 | 4855 of 4855 |
| patient linking | precision 0, recall 0 | **precision 0.97, recall 0.84, F0.5 0.94**; 1 wrong merge |
| records linked / generalised | 0 / 114 | 718 / 114 |
| raw copies | 0 | 0 |
| release gate | not run | 2 files re-scrubbed, 0 rejected |

The engine was developed against this practice data, so these numbers are an upper bound. Section 6
is the honest generalisation test.

Local attack lab (`tools/attack_lab`, approximations of `ATTACKS.md`, not official scores), produced
by `tools/studio/evidence.py`. The baseline is an unprotected copy of the same input files with the
same record locators, attacked in the same way.

| Attack | Unprotected copy | Anaam release | Note |
|---|---|---|---|
| A1 direct exposure | 81 of 240 (33.8%) | 11 of 240 (4.6%) | the 11 are all Aadhaar last-4 digits found inside other numbers or as a standalone 4-digit value; no full name or phone survives |
| A3 record linkage | 708 of 817 records with a registry candidate; mean top-candidate share 0.674 | 301 of 817; 0.683 | after the Hindi-header and age_sex generalisation (Omkar): far fewer records can be matched at all; confidence on those that can is about the same |
| A4 profile re-identification | 90 of 156 (57.7%) | 78 of 151 (51.7%) | the largest remaining privacy risk; unchanged with `min_group_size` 10 or 20 and 10-year bands |
| A5 targeted facts found | 5 of 18 (27.8%); global shift recoverable | **11 of 18 (61.1%)**; global shift not recoverable | higher than the baseline: linked pseudonyms let the attacker pool known facts across a patient's records. Needs work in the privacy layer |
| A6 pseudonym inversion | n/a | 0 of 48 | keyed HMAC |
| A7 cross-release | n/a | 0 stable pseudonyms; 0 of 817 date pairs coincide | a second run with a random secret (earlier runs measured 0.4% and 3.3%: coincidence varies with the secret) |

## 6. Held-out test (sealed chaos seeds, no tuning afterwards)

Seeds `holdout-1` and `holdout-2` (60 patients each) were generated and run once after the wiring
was finished. Names, labels, ID shapes, date formats and nesting do not appear in the practice data.
The generator was written by the engine's author, so this is a weaker test than data from a third party.

| Measure | holdout-1 | holdout-2 |
|---|---|---|
| files | 40 sanitized, 0 quarantined | 44 sanitized, 0 quarantined |
| contract | CONTRACT OK | CONTRACT OK |
| personal data still visible (`check_dev.py`) | 1 of 405 (0.2%) | 0 of 421 (0.0%) |
| strict token recall (`score_dev.py`, weighted macro) | 0.998 (one village missed) | 1.000 |
| canaries | 0 of 3 | 0 of 3 |
| medical values kept | 145 of 145 | 157 of 157 |
| records carrying a pseudonym | text 24/34, JSON 12/14, **CSV 0/8, TSV 0/8** | text 28/38, JSON 12/14, **CSV 0/8, TSV 0/8** |
| linking accuracy | **not measurable** | **not measurable** |

Correction (found while building the Release Studio): an earlier version of this section reported
"0 (no pseudonyms issued)". That 0.00 came from `check_dev.py`, which scores only units marked
`link: required`, and the chaos generator writes no patient labels at all (`patient: null` on every
unit). Linking accuracy on these seeds is therefore unmeasured, not zero. What the output does show:
text and JSON records receive pseudonyms, while CSV/TSV records with unseen identity headers receive
none, because `core.header_roles.find_patient_identity_column` does not recognise those columns (the
engine's field classifier does: `NAME_PATIENT`, `MRN`). The generator needs patient labels before
linking on unseen formats can be measured.

Update (commits `880fc5b`, `425e0b9`, re-measured at `4c30a6d`): CSV/TSV identity columns and JSON identity
keys that the header table does not recognise now fall back to the engine's field classifier. On the same two
seeds, records carrying a pseudonym are CSV 8/8 and 8/8, TSV 6/8 and 6/8, JSON 12/14 and 12/14, text 24/34 and
28/38; PII visible and medical values are unchanged (1 of 826; 302 of 302). On the practice data linking is now
precision 0.97, recall 0.90, F0.5 0.95 (1 wrong merge), and leaks, canaries and medical values are unchanged.

## 7. Official submission check

`check_submission.py --repo . --run` under WSL Ubuntu (Python 3.12.3, a `python` alias to `python3`
on `PATH`, which the `run` line needs): **READY TO SUBMIT**. Exit 0 in 18.1 s, CONTRACT OK,
identical output with the same secret, different output with a different secret, secret never
written, input unchanged. The only warning is the missing brief PDF.

Resources on Linux (`/usr/bin/time -v`, 200 practice files): 16.5 s wall clock, 48.2 MB peak
resident memory (`report.json`: 14.7 s, 47.1 MB). The event limit is 15 minutes per run.

On Windows the checker cannot run `main.py` when the path contains a space (POSIX quoting), and
`report.json` shows `peak_rss_mb: 0.0` because the `resource` module is unavailable there.

## 8. Test history

411 tests pass (76 pipeline unittest, 335 engine pytest including 18 integration and release-gate
tests). The import-layout commit was also checked out in an isolated worktree and passed on its own
(393 tests, `main.py` exit 0).
