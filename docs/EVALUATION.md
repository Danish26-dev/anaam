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

## 5. Official submission check

`check_submission.py --repo .`: quick mode prints READY TO SUBMIT (files only).
`check_submission.py --repo . --run`: **fails**, exit code 2, `main.py` does not exist.
It also confirms the secret was never written and the input was left unchanged.

## 6. Test history

317 tests pass. Each commit was also checked out in an isolated worktree and its own tests run:
23, 57, 143, 286, 294, 317 and 317 tests passed at the commits that contain tests (see `PROGRESS.md`).
