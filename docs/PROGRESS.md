# Progress log

Repository: `https://github.com/Danish26-dev/anaam`. Two lines of work were started from the same
LICENSE commit (`eaa359e`) and joined by an ordinary merge (`eace4a7`); no history was rewritten and
nothing was force-pushed.

## Pipeline line (Omkar), commits on `main` before the merge

`79eb6d9` scaffolding, `0a8e8de` core security layer, `18367e0` ingestion, `02c124a` format adapters,
`0bbc630` identity resolution, `456d213` privacy transforms, `b8000bc` writers and detection seam,
`027411f` `main.py`, `2c96037` local attack lab, `ffc9811` 76-test suite and documentation.

## Engine line (Danish), branch `feature/anaam-engine`

Each commit was checked out alone in a temporary worktree and its own tests run.

| Commit | Milestone | Tests at that commit |
|---|---|---|
| `8d03665` | chore: submission scaffold | none yet |
| `67818e0` | feat(core): shared interfaces (proposed; now superseded by `src/core/interfaces.py`, see `INTERFACE_NOTES.md`) | none yet |
| `492306b` | feat(detection): Unicode normalization and cross-script transliteration | 23 passed |
| `9a5933c` | feat(clinical): typed clinical span protection | 57 passed |
| `debd88f` | feat(detection): identifiers, dates, addresses, gazetteer | 143 passed |
| `b43aece` | feat(detection): names, identity lexicon, field classifier, span resolver, payloads | 286 passed |
| `2e7f9d8` | feat(detection): engine with hidden-channel sanitisation | 294 passed |
| `0139dfa` | feat(verify): independent release verifier | 317 passed |
| `99297af` | test: dev bench, chaos generator, identity audit | 317 passed |
| `14b19bb`, `59ebf94`, `4da269f` | docs: README, compliance records, commit hashes | 317 passed |
| `d7dff92` | test: move engine tests to `tests/engine` so the stdlib `unittest` command ignores them | 317 passed |

## Integration

| Commit | What | Verified |
|---|---|---|
| `eace4a7` | merge `origin/main` into the engine branch; 5 add/add conflicts resolved (see commit message) | pytest 393 passed; `unittest discover -s tests` OK with and without pytest; `main.py` exit 0; CONTRACT OK |
| `35b9f1f` | fix(audit): exempt documented example secrets from the secret rule | 393 passed; audit blocked=0 |
| `039333d`, `422d756` | docs: integration guide, corrected status, commit hashes | same |
| `e4727c2`..`5f745d6` | Omkar on `main`: contract reconciliation, plus the engine modules, tests, tools and docs re-committed from the engine branch (byte-identical modules and tests; docs equal to `4da269f`) | |
| `f64067b` | merge `origin/main` again: Omkar's `src/contracts.py` shim and `interfaces.py` kept; engine's newer docs and audit fix kept; 13 duplicate test files at `tests/` removed (identical to `tests/engine/`) | pytest 393 passed; `unittest discover -s tests` OK (76); `main.py` exit 0; CONTRACT OK |

`main` was then fast-forwarded to the engine branch and pushed normally.

## Wiring (branch `feature/engine-wiring`, from `main` at `4d38f34`)

| Commit | What | Verified |
|---|---|---|
| `a1d2478` | refactor(engine): pipeline import layout; `src/contracts.py` shim removed | checked out alone: 393 passed, unittest OK, `main.py` exit 0 |
| `31d16a6` | feat(detection): engine wired into `main.py` and the writers | 407 passed; `check_dev.py`: 0 of 3230 PII visible, 0 of 4 canaries, 4855/4855 medical, linking F0.5 0.94 |
| `ef86841` | feat(verify): release gate on every file before publication | 411 passed; 7 quarantined (broken inputs only), 2 re-scrubbed |
| `886b1b4` | docs: measured results, held-out test, brief | 411 passed; `check_submission.py --run` READY TO SUBMIT (WSL) |

## Problems found and fixed during the work

- The identity audit found 143 practice-data identities in the engine's own tests, tools and comments,
  including chaos name pools that collided with the practice canaries. They were replaced with invented values.
- The verifier exposed four sanitiser bugs, all fixed with tests: harmless headers renamed, digit groups
  across a line break, Devanagari generic name parts, a tab read as a label gap.
- After the merge, `unittest discover` without pytest failed with 8 import errors on the engine's pytest
  files. Fixed by moving them to `tests/engine/` before the merge.
- Wiring: JSON array-item fields are pointers relative to the item, so the first wiring passed full
  pointers and a third of lookups missed their context. A `None == None` comparison dropped every span
  on unrecognised columns (28% leaked on one run). A latent `KeyError` in `main.py` appeared once records
  were linked. A JSON number holding an Aadhaar was passed through. All fixed with tests.
- Release gate: letters inside a pseudonym's code spelled a harvested name, so the gate flagged it and
  the re-scrub cut the pseudonym; ward numbers in addresses counted as clinical loss; a UUID starting
  `81cc-` read as a dose. 39 good files were rejected before these fixes, 0 after.
- The first wiring commit staged only the shim deletion (a deleted path made `git add` fail). The two
  unpushed local commits were rebuilt with `git reset --soft`; nothing pushed was rewritten.

- Released TSV corruption (reported by Omkar, reproduced on `fb8a368`, fixed in `227ca2f`): the release
  gate re-scrubbed `registration/jeevanjyoti_patients.tsv` as one flat string; a phone-shaped span that
  crossed a tab (digits ending one cell and starting the next) was replaced with the tab, so 7 of 31 rows
  had 13 cells instead of 14, and the structure check (row count and header width only) passed it.
  Now every row's width is compared with the input, the rescrub works cell by cell, and CSV/TSV are
  scanned cell by cell. The kit's `validate_output.py` and `check_submission.py` did not detect it.

## Open items

1. Linking on unseen formats: held-out CSV/TSV records get no pseudonym (`find_patient_identity_column`); accuracy unmeasured until the chaos generator writes patient labels. (An earlier "no pseudonyms" claim was a measurement artefact; see EVALUATION section 6.)
2. Local A4 profile re-identification at 51.0%; not moved by the policy knobs.
3. Practice values in two pipeline docstrings and two pipeline test files; kit scripts committed.
4. Brief PDF is a draft for team review; the held-out data was written by the detector's author.
5. Review and merge `feature/engine-wiring` into `main` (pull request, reviewed by Omkar).
