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
| next | merge `origin/main` again: Omkar's `src/contracts.py` shim and `interfaces.py` kept; engine's newer docs and audit fix kept; 13 duplicate test files at `tests/` removed (identical to `tests/engine/`) | pytest 393 passed; `unittest discover -s tests` OK (76); `main.py` exit 0; CONTRACT OK |

`main` was then fast-forwarded to the engine branch and pushed normally.

## Problems found and fixed during the work

- The identity audit found 143 practice-data identities in the engine's own tests, tools and comments,
  including chaos name pools that collided with the practice canaries. They were replaced with invented values.
- The verifier exposed four sanitiser bugs, all fixed with tests: harmless headers renamed, digit groups
  across a line break, Devanagari generic name parts, a tab read as a label gap.
- After the merge, `unittest discover` without pytest failed with 8 import errors on the engine's pytest
  files. Fixed by moving them to `tests/engine/` before the merge.

## Open blockers

1. The engine is not wired into `main.py` (`docs/INTERFACE_NOTES.md` lists every change needed).
   Until then the release relies on the regex stub: 73.9% of practice PII visible, 4 of 4 canaries leaked, no linking.
2. Contract: Omkar's reconciliation is in. Danish still has to switch the engine's imports, map the
   stub's lower-case actions, and remove the `src/contracts.py` shim.
3. `check_submission.py --run` not confirmed: needs a Linux or WSL run.
4. Practice values in two pipeline docstrings and two pipeline test files; kit scripts committed.
5. No sealed holdout, no peak-memory figure, no brief PDF.
